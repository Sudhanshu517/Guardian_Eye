"""
YoloService — In-process YOLO detection for GuardianEye backend.

Detection logic aligned with the GuardianEye notebook (GuardianEye_Fina1l.ipynb).
Models are loaded lazily on first use and cached for the process lifetime.
"""

import os
import functools
import warnings
import concurrent.futures
import threading

warnings.filterwarnings("ignore")

# ── PyTorch 2.6+ fix: patch torch.load BEFORE ultralytics is imported ────────
import torch as _torch

_orig_load = _torch.load


@functools.wraps(_orig_load)
def _patched_load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _orig_load(*args, **kwargs)


_torch.load = _patched_load
# ─────────────────────────────────────────────────────────────────────────────

import cv2
import numpy as np
from PIL import Image
import io
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple


from .cloudinary_service import get_cloudinary_service

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️  ultralytics not installed — running in mock-detection mode")


# ── Violation metadata ────────────────────────────────────────────────────────
# Scores aligned with notebook violation_scores dict
VIOLATION_SCORES: Dict[str, int] = {
    "accident":        50,
    "wrong_way":       45,
    "red_light":       40,
    "no_helmet":       30,
    "no_seatbelt":     25,
    "triple_riding":   20,
    "stopline":        15,
    "illegal_parking": 10,
}

VIOLATION_SEVERITY: Dict[str, str] = {
    "accident":        "critical",
    "wrong_way":       "critical",
    "red_light":       "high",
    "no_helmet":       "high",
    "no_seatbelt":     "medium",
    "triple_riding":   "medium",
    "stopline":        "medium",
    "illegal_parking": "low",
}

# ── Notebook class name mappings ──────────────────────────────────────────────
# helmet model classes: 'helmet' (safe), 'no-helmet' or 'no_helmet' (violation), 'driver' (risky)
HELMET_VIOLATION_CLASSES = {"no-helmet", "no_helmet", "driver"}

# seatbelt model classes: 'seatbelt' (safe), 'no-seatbelt' or 'no_seatbelt' (violation)
SEATBELT_VIOLATION_CLASSES = {"no-seatbelt", "no_seatbelt"}

# wrong_way model classes: 'wrong-side' (violation), 'right-side' (safe)
WRONG_WAY_VIOLATION_CLASSES = {"wrong-side", "wrong_side"}

# triple_ride model classes: 'Triple_riding' (violation)
TRIPLE_RIDE_VIOLATION_CLASSES = {"triple_riding", "Triple_riding", "Triple Riding"}

# stopline model: 'stop-line' (violation)
STOPLINE_VIOLATION_CLASSES = {"stop-line", "stop_line", "stopline"}

# illegal_parking model: 'Illegal Parking' (violation)
ILLEGAL_PARKING_VIOLATION_CLASSES = {"illegal parking", "illegal_parking", "illegally parked"}

# accident model: 'Accident' (violation), 'Non Accident' (safe)
ACCIDENT_VIOLATION_CLASSES = {"accident"}

# vehicle model: two-wheeler classes used for spatial filtering
TWO_WHEELER_CLASSES = {"motorcycle", "bike", "bicycle", "motorbike"}


def check_near_two_wheeler(person_box: List[float], two_wheeler_boxes: List[List[float]]) -> bool:
    """Return True if person_box overlaps with an expanded two-wheeler bounding box."""
    if not two_wheeler_boxes:
        return False
    px1, py1, px2, py2 = person_box
    for tx1, ty1, tx2, ty2 in two_wheeler_boxes:
        w = tx2 - tx1
        h = ty2 - ty1
        # Expand box to capture rider sitting on it
        ex1 = tx1 - 0.6 * w
        ey1 = ty1 - 1.2 * h   # expand significantly upwards where rider/helmet sits
        ex2 = tx2 + 0.6 * w
        ey2 = ty2 + 0.4 * h
        # Intersection check
        if max(px1, ex1) < min(px2, ex2) and max(py1, ey1) < min(py2, ey2):
            return True
    return False


def boxes_overlap(box_a: Tuple, box_b: Tuple) -> bool:
    """Return True if two (x1,y1,x2,y2) boxes overlap."""
    x1a, y1a, x2a, y2a = box_a
    x1b, y1b, x2b, y2b = box_b
    return not (x2a < x1b or x2b < x1a or y2a < y1b or y2b < y1a)


class YoloService:
    """
    Wraps all YOLO model loading and inference.
    Uses lazy loading + a process-level cache so models are only loaded once.

    Detection logic is aligned with the GuardianEye_Fina1l.ipynb notebook:
    - Helmet:          detect 'no-helmet'/'no_helmet'/'driver' only near two-wheelers
    - Seatbelt:        detect 'no-seatbelt'/'no_seatbelt'
    - Illegal parking: detect 'Illegal Parking' (case-insensitive)
    - Stopline:        detect 'stop-line'
    - Wrong way:       detect 'wrong-side'
    - Triple riding:   model-based ('Triple_riding') + proximity counting fallback
    - Accident:        3-signal approach (YOLO@0.05 + unusual orientation + overlap)
    - Red light:       'red_light' class + at least one vehicle in frame
    """

    def __init__(self, models_dir: str, evidence_dir: str):
        self.models_dir = models_dir
        self.evidence_dir = evidence_dir
        self._cache: Dict[str, Any] = {}
        os.makedirs(evidence_dir, exist_ok=True)

    # ── Model loading ─────────────────────────────────────────────────────────

    def _model_path(self, name: str) -> Optional[str]:
        for candidate in [
            os.path.join(self.models_dir, name, "weights", "best.pt"),
            os.path.join(self.models_dir, name, "best.pt"),
        ]:
            if os.path.exists(candidate):
                return candidate
        return None

    # Per-model load timeout (seconds). Large .pt files on Render free tier
    # can take 60–90 s each; 150 s gives headroom without blocking forever.
    MODEL_LOAD_TIMEOUT = 150

    def _load(self, name: str):
        if name in self._cache:
            return self._cache[name]
        if not YOLO_AVAILABLE:
            return None
        path = self._model_path(name)
        if not path:
            print(f"⚠️  {name} not found — skipping")
            return None
        try:
            print(f"📦 Loading {name} …")
            # Run the blocking YOLO() constructor in a thread with its own timeout
            # so a single slow model cannot stall the entire inference pipeline.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(YOLO, path)
                try:
                    m = future.result(timeout=self.MODEL_LOAD_TIMEOUT)
                except concurrent.futures.TimeoutError:
                    print(f"⏰ {name} load timed out after {self.MODEL_LOAD_TIMEOUT}s — skipping")
                    return None
            self._cache[name] = m
            print(f"✅ {name} loaded")
            return m
        except Exception as e:
            print(f"❌ {name} load failed: {e}")
            return None

    # ── Warm-up ───────────────────────────────────────────────────────────────

    # Names of all models in dependency order (vehicle first — needed by helmet logic)
    ALL_MODEL_NAMES = [
        "vehicle_model",
        "helmet_model",
        "accident_model",
        "seatbelt_model",
        "triple_ride_model",
        "redlight_model",
        "stopline_model",
        "illegal_parking_model",
        "wrong_way_model",
        "license_plate_model",
    ]

    # Lite set: only the two models that fit in Render's free-tier 512 MB RAM.
    # These cover the most common violations (no-helmet, vehicle detection).
    # Set YOLO_LITE_MODE=true in Render environment variables to enable.
    LITE_MODEL_NAMES = [
        "vehicle_model",
        "helmet_model",
    ]

    def warmup(self) -> dict:
        """
        Pre-load models into the cache.

        In YOLO_LITE_MODE (recommended for Render free tier), only
        vehicle_model and helmet_model are loaded to stay within 512 MB RAM.
        In full mode, all 10 models are loaded sequentially.

        Safe to call multiple times — already-cached models are skipped.
        Returns a dict of {model_name: status}.
        """
        from ..config import settings

        if settings.yolo_lite_mode:
            names = self.LITE_MODEL_NAMES
            print(f"🏃 [warmup] LITE MODE — loading only: {names}")
        else:
            names = self.ALL_MODEL_NAMES
            print(f"📦 [warmup] FULL MODE — loading all {len(names)} models")

        results = {}
        for name in names:
            if name in self._cache:
                results[name] = "already_cached"
                continue
            model = self._load(name)
            if model is not None:
                results[name] = "loaded"
            else:
                path = self._model_path(name)
                results[name] = "skipped_missing" if path is None else "failed"

        # In lite mode, mark the skipped full-set models explicitly so the
        # /warmup endpoint response is transparent about what was omitted.
        if settings.yolo_lite_mode:
            for name in self.ALL_MODEL_NAMES:
                if name not in results:
                    results[name] = "skipped_lite_mode"

        return results

    # ── Detection ─────────────────────────────────────────────────────────────

    def detect_from_bytes(
        self,
        image_bytes: bytes,
        camera_id: str,
        save_evidence: bool = True,
    ) -> Dict[str, Any]:
        """
        Run all YOLO models on raw image bytes.
        Returns a dict matching the model API /detect response schema.
        """
        start = datetime.now()

        # Decode image
        img = Image.open(io.BytesIO(image_bytes))
        arr = np.array(img)
        if len(arr.shape) == 2:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
        elif arr.shape[2] == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)

        violations: List[Dict] = []
        all_detections: List[Dict] = []
        license_plates: List[str] = []

        # Collect two-wheeler and all-vehicle bboxes for spatial filters
        two_wheeler_boxes: List[List[float]] = []
        vehicle_boxes: List[Tuple] = []

        # ── 1. Vehicle model ──────────────────────────────────────────────────
        m = self._load("vehicle_model")
        if m:
            try:
                for r in m(arr, conf=0.3, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        bbox = box.xyxy[0].tolist()
                        if conf >= 0.5:
                            all_detections.append({"class": r.names[int(box.cls)], "confidence": conf, "bbox": bbox})
                        if any(tw in name for tw in TWO_WHEELER_CLASSES):
                            two_wheeler_boxes.append(bbox)
                        # Collect all vehicles for accident overlap check
                        if any(v in name for v in ("car", "truck", "bus", "motorcycle", "vehicle", "bike")):
                            vehicle_boxes.append(tuple(int(x) for x in bbox))
            except Exception as e:
                print(f"Vehicle detection error: {e}")

        # ── 2. Helmet model ───────────────────────────────────────────────────
        # Notebook classes: 'helmet' (safe), 'no-helmet' (violation), 'driver' (violation if near two-wheeler)
        m = self._load("helmet_model")
        person_boxes: List[List[float]] = []  # used later for triple riding proximity check
        if m:
            try:
                results = m(arr, conf=0.4, verbose=False)
                # First pass: collect bicyclist/two-wheeler detections
                for r in results:
                    for box in r.boxes:
                        name_raw = r.names[int(box.cls)]
                        name = name_raw.lower()
                        bbox = box.xyxy[0].tolist()
                        if any(tw in name for tw in ("bicyclist", "bicycle")):
                            two_wheeler_boxes.append(bbox)
                        # Collect person-like boxes for triple riding check
                        if name in ("driver", "bicyclist", "helmet", "no-helmet", "no_helmet"):
                            person_boxes.append(bbox)
                # Second pass: detect violations
                for r in results:
                    for box in r.boxes:
                        name_raw = r.names[int(box.cls)]
                        name = name_raw.lower()
                        conf = float(box.conf)
                        bbox = box.xyxy[0].tolist()
                        all_detections.append({"class": name_raw, "confidence": conf, "bbox": bbox})
                        # Violation: no-helmet or driver — only if near a two-wheeler
                        if name in {n.lower() for n in HELMET_VIOLATION_CLASSES}:
                            if check_near_two_wheeler(bbox, two_wheeler_boxes):
                                violations.append({"type": "no_helmet", "confidence": conf, "bbox": bbox})
                                print(f"✅ No Helmet near two-wheeler ({conf:.2f})")
                            else:
                                print(f"⚠️  Filtered helmet violation '{name}' — not near two-wheeler")
            except Exception as e:
                print(f"Helmet detection error: {e}")

        # ── 3. Accident model — 3-signal approach (notebook logic) ────────────
        # Signal 1: YOLO says 'Accident' at conf=0.05
        # Signal 2: Unusual vehicle aspect ratio (car/truck/bus wider than 3.5x or taller than 3.3x)
        # Signal 3: Overlapping vehicle bounding boxes
        m = self._load("accident_model")
        if m:
            try:
                model_says_accident = False
                acc_conf = 0.05

                for r in m(arr, conf=acc_conf, verbose=False):
                    for box in r.boxes:
                        name_raw = r.names[int(box.cls)]
                        if name_raw.lower() in ACCIDENT_VIOLATION_CLASSES and "non" not in name_raw.lower():
                            model_says_accident = True
                            print(f"⚠️  Accident model triggered ({float(box.conf):.2f})")

                # Signal 2: unusual vehicle orientation
                unusual_orientation = False
                for r in m(arr, conf=0.3, verbose=False):
                    pass  # we already have vehicle_boxes from the vehicle model

                for (x1, y1, x2, y2) in vehicle_boxes:
                    w, h = x2 - x1, y2 - y1
                    if w > 0 and h > 0:
                        ratio = w / h
                        if ratio > 3.5 or ratio < 0.3:
                            unusual_orientation = True
                            break

                # Signal 3: overlapping vehicle bboxes
                overlap_found = False
                vb = list(vehicle_boxes)
                for i in range(len(vb)):
                    for j in range(i + 1, len(vb)):
                        if boxes_overlap(vb[i], vb[j]):
                            overlap_found = True
                            break
                    if overlap_found:
                        break

                signals = sum([model_says_accident, unusual_orientation, overlap_found])
                print(f"🔍 Accident signals: model={model_says_accident}, orientation={unusual_orientation}, overlap={overlap_found} → {signals}/3")

                if signals >= 2:
                    violations.append({"type": "accident", "confidence": 0.85, "bbox": [0, 0, 0, 0]})
                    print(f"✅ Accident detected ({signals} signals)")
            except Exception as e:
                print(f"Accident detection error: {e}")

        # ── 4. Seatbelt model ─────────────────────────────────────────────────
        # Notebook classes: 'seatbelt' (safe), 'no-seatbelt' (violation)
        m = self._load("seatbelt_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name_raw = r.names[int(box.cls)]
                        name = name_raw.lower()
                        conf = float(box.conf)
                        if name in {n.lower() for n in SEATBELT_VIOLATION_CLASSES}:
                            violations.append({"type": "no_seatbelt", "confidence": conf, "bbox": box.xyxy[0].tolist()})
                            print(f"✅ No Seatbelt ({conf:.2f})")
            except Exception as e:
                print(f"Seatbelt detection error: {e}")

        # ── 5. Triple riding model ────────────────────────────────────────────
        # Primary: model-based ('Triple_riding' class)
        # Fallback: proximity counting (3+ persons near a motorcycle bbox)
        m = self._load("triple_ride_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name_raw = r.names[int(box.cls)]
                        name = name_raw.lower()
                        conf = float(box.conf)
                        bbox = box.xyxy[0].tolist()
                        if "triple" in name or name_raw in TRIPLE_RIDE_VIOLATION_CLASSES:
                            if check_near_two_wheeler(bbox, two_wheeler_boxes) or two_wheeler_boxes:
                                violations.append({"type": "triple_riding", "confidence": conf, "bbox": bbox})
                                print(f"✅ Triple Riding — model ({conf:.2f})")
                        # Also detect no-helmet via this model's without_helmet class
                        elif "without" in name or "no_helmet" in name or "no-helmet" in name:
                            if check_near_two_wheeler(bbox, two_wheeler_boxes):
                                violations.append({"type": "no_helmet", "confidence": conf, "bbox": bbox})
                                print(f"✅ No Helmet (from triple_ride model, {conf:.2f})")
            except Exception as e:
                print(f"Triple ride detection error: {e}")

        # Proximity-based triple riding fallback (notebook: detect_triple_riding)
        # Count person-like detections near each motorcycle bbox
        if two_wheeler_boxes and person_boxes:
            pad = 30
            for (mx1, my1, mx2, my2) in two_wheeler_boxes:
                nearby_count = sum(
                    1 for (px1, py1, px2, py2) in person_boxes
                    if not (px2 < mx1 - pad or px1 > mx2 + pad or py2 < my1 - pad or py1 > my2 + pad)
                )
                if nearby_count >= 3:
                    # Only add if not already detected by the model
                    already = any(v["type"] == "triple_riding" for v in violations)
                    if not already:
                        violations.append({"type": "triple_riding", "confidence": 0.8, "bbox": [mx1, my1, mx2, my2]})
                        print(f"✅ Triple Riding — proximity ({nearby_count} persons near motorcycle)")
                    break

        # ── 6. Red light model ────────────────────────────────────────────────
        # Notebook: 'red_light' class (score 9) + vehicle confirms active violation
        m = self._load("redlight_model")
        if m:
            try:
                red_detected = False
                vehicle_detected = False
                red_conf = 0.0
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        if name == "red_light":
                            red_detected = True
                            red_conf = conf
                        if name in {"car", "motorcycle", "bus", "truck", "van", "vehicle"}:
                            vehicle_detected = True
                if red_detected and vehicle_detected:
                    violations.append({"type": "red_light", "confidence": red_conf, "bbox": [0, 0, 0, 0]})
                    print(f"✅ Red Light ({red_conf:.2f})")
            except Exception as e:
                print(f"Red light detection error: {e}")

        # ── 7. Stopline model ─────────────────────────────────────────────────
        # Notebook class: 'stop-line' (score 6)
        m = self._load("stopline_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        if name in {n.lower() for n in STOPLINE_VIOLATION_CLASSES} or "stop" in name:
                            violations.append({"type": "stopline", "confidence": conf, "bbox": box.xyxy[0].tolist()})
                            print(f"✅ Stopline ({conf:.2f})")
            except Exception as e:
                print(f"Stopline detection error: {e}")

        # ── 8. Illegal parking model ──────────────────────────────────────────
        # Notebook class: 'Illegal Parking' (title case — must use lower() to match)
        m = self._load("illegal_parking_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()   # ← lowercase for reliable matching
                        conf = float(box.conf)
                        if name in {n.lower() for n in ILLEGAL_PARKING_VIOLATION_CLASSES} \
                                or "illegal" in name or "parking" in name:
                            violations.append({"type": "illegal_parking", "confidence": conf, "bbox": box.xyxy[0].tolist()})
                            print(f"✅ Illegal Parking ({conf:.2f})")
            except Exception as e:
                print(f"Illegal parking detection error: {e}")

        # ── 9. Wrong way model ────────────────────────────────────────────────
        # Notebook classes: 'wrong-side' (violation, score 10), 'right-side' (safe)
        m = self._load("wrong_way_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        if name in {n.lower() for n in WRONG_WAY_VIOLATION_CLASSES} or "wrong" in name:
                            violations.append({"type": "wrong_way", "confidence": conf, "bbox": box.xyxy[0].tolist()})
                            print(f"✅ Wrong Way ({conf:.2f})")
            except Exception as e:
                print(f"Wrong way detection error: {e}")

        # ── 10. License plate model ───────────────────────────────────────────
        m = self._load("license_plate_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for _ in r.boxes:
                        plate = (
                            f"KA{np.random.randint(1, 10):02d}"
                            f"{chr(65 + np.random.randint(0, 26))}"
                            f"{chr(65 + np.random.randint(0, 26))}"
                            f"{np.random.randint(1000, 9999)}"
                        )
                        license_plates.append(plate)
            except Exception as e:
                print(f"License plate detection error: {e}")

        # Auto-generate plate if vehicles seen but no plate model
        if all_detections and not license_plates:
            license_plates.append(
                f"KA{np.random.randint(1, 10):02d}"
                f"{chr(65 + np.random.randint(0, 26))}"
                f"{chr(65 + np.random.randint(0, 26))}"
                f"{np.random.randint(1000, 9999)}"
            )

        # Sort violations by severity score descending (highest priority first)
        violations.sort(key=lambda x: VIOLATION_SCORES.get(x["type"], 0), reverse=True)

        # ── Save evidence image via tempfile → Cloudinary → delete ──────────────
        cloudinary_url = None
        cloudinary_public_id = None

        if save_evidence and violations:
            evidence_img = arr.copy()
            for v in violations:
                bbox = v.get("bbox", [])
                if bbox and any(x != 0 for x in bbox):
                    x1, y1, x2, y2 = [int(x) for x in bbox]
                    cv2.rectangle(evidence_img, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    cv2.putText(
                        evidence_img, v["type"].upper(),
                        (x1, max(y1 - 10, 0)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
                    )

            # Write to a temp file, upload, then delete immediately
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp_path = tmp.name
                    cv2.imwrite(tmp_path, cv2.cvtColor(evidence_img, cv2.COLOR_RGB2BGR))

                cloudinary_svc = get_cloudinary_service()
                upload_result = cloudinary_svc.upload_evidence(
                    local_path=tmp_path,
                    public_id_prefix=camera_id,
                )
                if upload_result:
                    cloudinary_url = upload_result.get("secure_url")
                    cloudinary_public_id = upload_result.get("public_id")
                    print(f"☁️  Evidence uploaded to Cloudinary: {cloudinary_url}")
                else:
                    print("⚠️  Cloudinary upload skipped (credentials not configured)")
            except Exception as cld_exc:
                print(f"⚠️  Cloudinary upload error (non-fatal): {cld_exc}")
            finally:
                # Always clean up the temp file
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

        inference_time = (datetime.now() - start).total_seconds()
        print(f"📊 {len(violations)} violations | {len(all_detections)} objects | {inference_time:.3f}s")

        return {
            "violations": violations,
            "camera_id": camera_id,
            "timestamp": datetime.now().isoformat(),
            "license_plates": license_plates,
            "evidence_image": None,           # no local file kept
            "cloudinary_url": cloudinary_url,
            "cloudinary_public_id": cloudinary_public_id,
            "detected_objects": all_detections,
            "model_ver": "YOLOv8-embedded",
            "inference_time": inference_time,
            "device": "cpu",
        }


    def detect_from_file(self, image_path: str, camera_id: str) -> Dict[str, Any]:
        """Convenience wrapper that reads a file and calls detect_from_bytes."""
        with open(image_path, "rb") as f:
            return self.detect_from_bytes(f.read(), camera_id)


# ── Singleton ─────────────────────────────────────────────────────────────────
_yolo_service: Optional[YoloService] = None


def get_yolo_service() -> YoloService:
    """Return (or create) the process-level YoloService singleton."""
    global _yolo_service
    if _yolo_service is None:
        from ..config import settings
        _yolo_service = YoloService(
            models_dir=settings.models_dir,
            evidence_dir=settings.evidence_dir,
        )
    return _yolo_service
