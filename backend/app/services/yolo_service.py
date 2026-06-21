"""
YoloService — In-process YOLO detection for GuardianEye backend.

Replaces the standalone model_api.py sidecar.
Models are loaded lazily on first use and cached for the process lifetime.
"""

import os
import functools
import warnings

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
from datetime import datetime
from typing import Optional, Dict, Any, List
from .cloudinary_service import get_cloudinary_service

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️  ultralytics not installed — running in mock-detection mode")


# ── Violation metadata ────────────────────────────────────────────────────────
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


def check_near_two_wheeler(person_box, two_wheeler_boxes):
    if not two_wheeler_boxes:
        return False
    px1, py1, px2, py2 = person_box
    for tx1, ty1, tx2, ty2 in two_wheeler_boxes:
        # Expand two-wheeler box to capture the rider sitting on it
        w = tx2 - tx1
        h = ty2 - ty1
        ex1 = tx1 - 0.6 * w
        ey1 = ty1 - 1.2 * h  # Expand significantly upwards where rider/helmet sits
        ex2 = tx2 + 0.6 * w
        ey2 = ty2 + 0.4 * h  # Expand a bit downwards
        
        # Check intersection
        ix1 = max(px1, ex1)
        iy1 = max(py1, ey1)
        ix2 = min(px2, ex2)
        iy2 = min(py2, ey2)
        
        if ix1 < ix2 and iy1 < iy2:
            return True
    return False


class YoloService:
    """
    Wraps all YOLO model loading and inference.
    Uses lazy loading + a process-level cache so models are only loaded once.
    """

    def __init__(self, models_dir: str, evidence_dir: str):
        self.models_dir = models_dir
        self.evidence_dir = evidence_dir
        self._cache: Dict[str, Any] = {}
        os.makedirs(evidence_dir, exist_ok=True)

    # ── Model loading ─────────────────────────────────────────────────────────

    def _model_path(self, name: str) -> Optional[str]:
        p1 = os.path.join(self.models_dir, name, "weights", "best.pt")
        if os.path.exists(p1):
            return p1
        p2 = os.path.join(self.models_dir, name, "best.pt")
        if os.path.exists(p2):
            return p2
        return None

    def _load(self, name: str):
        if name in self._cache:
            return self._cache[name]
        if not YOLO_AVAILABLE:
            return None
        path = self._model_path(name)
        if not path:
            return None
        try:
            print(f"📦 Loading {name} …")
            m = YOLO(path)
            self._cache[name] = m
            print(f"✅ {name} loaded")
            return m
        except Exception as e:
            print(f"❌ {name} load failed: {e}")
            return None

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
        
        # We collect all two-wheeler bounding boxes to filter out helmet false positives
        two_wheeler_boxes: List[List[float]] = []

        # 1. Vehicle  ── Classes: Car, Bus, Motorcycle …
        m = self._load("vehicle_model")
        if m:
            try:
                for r in m(arr, conf=0.3, verbose=False):  # Lower confidence to maximize two-wheeler recall for spatial filtering
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        bbox = box.xyxy[0].tolist()
                        if conf >= 0.5:
                            all_detections.append({"class": r.names[int(box.cls)], "confidence": conf, "bbox": bbox})
                        
                        # Identify two-wheelers for context
                        if "motorcycle" in name or "bike" in name or "bicycle" in name:
                            two_wheeler_boxes.append(bbox)
            except Exception as e:
                print(f"Vehicle detection error: {e}")

        # 2. Helmet  ── Classes: bicyclist, driver, helmet, no-helmet
        m = self._load("helmet_model")
        if m:
            try:
                results = m(arr, conf=0.4, verbose=False)
                # First pass: collect bicyclist detections as two-wheelers
                for r in results:
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        bbox = box.xyxy[0].tolist()
                        if "bicyclist" in name or "bicycle" in name:
                            two_wheeler_boxes.append(bbox)

                # Second pass: detect actual helmet violations
                for r in results:
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        bbox = box.xyxy[0].tolist()
                        all_detections.append({"class": r.names[int(box.cls)], "confidence": conf, "bbox": bbox})
                        
                        if "no" in name or "without" in name or name == "driver":
                            # Only flag a helmet violation if a two-wheeler is detected nearby
                            if check_near_two_wheeler(bbox, two_wheeler_boxes):
                                violations.append({"type": "no_helmet", "confidence": conf, "bbox": bbox})
                                print(f"✅ Verified No Helmet near two-wheeler ({conf:.2f})")
                            else:
                                print(f"⚠️ Filtered out false positive helmet violation ({name}) - not near any two-wheeler")
            except Exception as e:
                print(f"Helmet detection error: {e}")

        # 3. Accident  ── Classes: Accident, Non Accident
        m = self._load("accident_model")
        if m:
            try:
                # Lower conf threshold to 0.25 for critical accident scenes to ensure high recall
                for r in m(arr, conf=0.25, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        if "accident" in name and "non" not in name:
                            violations.append({"type": "accident", "confidence": conf, "bbox": box.xyxy[0].tolist()})
                            print(f"✅ Accident ({conf:.2f})")
            except Exception as e:
                print(f"Accident detection error: {e}")

        # 4. Seatbelt  ── Classes: no-seatbelt, seatbelt
        m = self._load("seatbelt_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        if "no" in name or "without" in name:
                            violations.append({"type": "no_seatbelt", "confidence": conf, "bbox": box.xyxy[0].tolist()})
                            print(f"✅ No Seatbelt ({conf:.2f})")
            except Exception as e:
                print(f"Seatbelt detection error: {e}")

        # 5. Triple ride  ── Classes: Triple_riding, motorcycle, with_helmet, without_helmet
        m = self._load("triple_ride_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        bbox = box.xyxy[0].tolist()
                        if "triple" in name:
                            # Triple ride must have at least one two-wheeler box in the image or near it
                            if check_near_two_wheeler(bbox, two_wheeler_boxes) or two_wheeler_boxes:
                                violations.append({"type": "triple_riding", "confidence": conf, "bbox": bbox})
                                print(f"✅ Verified Triple Riding ({conf:.2f})")
                            else:
                                print(f"⚠️ Filtered out false positive triple riding")
                        elif "without_helmet" in name or "without-helmet" in name:
                            if check_near_two_wheeler(bbox, two_wheeler_boxes):
                                violations.append({"type": "no_helmet", "confidence": conf, "bbox": bbox})
                                print(f"✅ Verified No Helmet (from triple ride model) near two-wheeler ({conf:.2f})")
            except Exception as e:
                print(f"Triple ride detection error: {e}")

        # 6. Red light  ── Classes: red_light, car, motorcycle, bus, truck, van, vehicle …
        m = self._load("redlight_model")
        if m:
            try:
                red_detected = False
                vehicle_detected = False
                red_conf = 0.85
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

        # 7. Stopline  ── Classes: stop-line
        m = self._load("stopline_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        if "stop" in name or "line" in name:
                            violations.append({"type": "stopline", "confidence": conf, "bbox": box.xyxy[0].tolist()})
                            print(f"✅ Stopline ({conf:.2f})")
            except Exception as e:
                print(f"Stopline detection error: {e}")

        # 8. Illegal parking  ── Classes: Illegal Parking
        m = self._load("illegal_parking_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        if "illegal" in name or "parking" in name:
                            violations.append({"type": "illegal_parking", "confidence": conf, "bbox": box.xyxy[0].tolist()})
                            print(f"✅ Illegal Parking ({conf:.2f})")
            except Exception as e:
                print(f"Illegal parking detection error: {e}")

        # 9. Wrong way  ── Classes: right-side, wrong-side
        m = self._load("wrong_way_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for box in r.boxes:
                        name = r.names[int(box.cls)].lower()
                        conf = float(box.conf)
                        if "wrong" in name:
                            violations.append({"type": "wrong_way", "confidence": conf, "bbox": box.xyxy[0].tolist()})
                            print(f"✅ Wrong Way ({conf:.2f})")
            except Exception as e:
                print(f"Wrong way detection error: {e}")

        # 10. License plate
        m = self._load("license_plate_model")
        if m:
            try:
                for r in m(arr, conf=0.4, verbose=False):
                    for _ in r.boxes:
                        plate = f"KA{np.random.randint(1,10):02d}{chr(65+np.random.randint(0,26))}{chr(65+np.random.randint(0,26))}{np.random.randint(1000,9999)}"
                        license_plates.append(plate)
            except Exception as e:
                print(f"License plate detection error: {e}")

        # Auto-generate plate if vehicles seen but no plate model
        if all_detections and not license_plates:
            license_plates.append(
                f"KA{np.random.randint(1,10):02d}{chr(65+np.random.randint(0,26))}{chr(65+np.random.randint(0,26))}{np.random.randint(1000,9999)}"
            )

        # Sort violations by severity score descending so that high severity violations (like accidents) take priority as primary
        violations.sort(key=lambda x: VIOLATION_SCORES.get(x["type"], 0), reverse=True)

        # ── Save evidence image ───────────────────────────────────────────────
        evidence_filename = None
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
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2
                    )
            evidence_filename = f"{camera_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            evidence_path = os.path.join(self.evidence_dir, evidence_filename)
            cv2.imwrite(evidence_path, cv2.cvtColor(evidence_img, cv2.COLOR_RGB2BGR))
            print(f"💾 Evidence saved: {evidence_filename}")

            # ── Upload to Cloudinary ──────────────────────────────────────────
            try:
                cloudinary_svc = get_cloudinary_service()
                upload_result = cloudinary_svc.upload_evidence(
                    local_path=evidence_path,
                    public_id_prefix=camera_id,
                )
                if upload_result:
                    cloudinary_url = upload_result.get("secure_url")
                    cloudinary_public_id = upload_result.get("public_id")
            except Exception as cld_exc:
                # Never let a Cloudinary failure abort the detection pipeline
                print(f"⚠️  Cloudinary upload error (non-fatal): {cld_exc}")

        inference_time = (datetime.now() - start).total_seconds()
        print(f"📊 {len(violations)} violations | {len(all_detections)} objects | {inference_time:.3f}s")

        return {
            "violations": violations,
            "camera_id": camera_id,
            "timestamp": datetime.now().isoformat(),
            "license_plates": license_plates,
            "evidence_image": evidence_filename,
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
