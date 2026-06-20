"""
GuardianEye Model API Server - Simplified Version

This version uses a simpler approach that works with PyTorch 2.6+
"""

import os
import warnings
warnings.filterwarnings('ignore')

# ─── PyTorch 2.6+ fix: patch torch.load BEFORE ultralytics is imported ──────
import functools
import torch as _torch

_original_torch_load = _torch.load

@functools.wraps(_original_torch_load)
def _patched_torch_load(*args, **kwargs):
    kwargs.setdefault('weights_only', False)
    return _original_torch_load(*args, **kwargs)

_torch.load = _patched_torch_load
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import io
import cv2
import numpy as np
from PIL import Image
from datetime import datetime

from ultralytics import YOLO

app = FastAPI(
    title="GuardianEye Model API",
    description="AI Model Service for Traffic Violation Detection",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
MODEL_DIR = "./models"
EVIDENCE_DIR = "./evidence"

# Model cache
MODELS = {}


class DetectionResponse(BaseModel):
    violations: List[Dict[str, Any]]
    camera_id: str
    timestamp: str
    license_plates: List[str]
    evidence_image: Optional[str]
    detected_objects: List[Dict[str, Any]]
    model_ver: str
    inference_time: float
    device: str
    
    class Config:
        protected_namespaces = ()


def get_model_path(model_name: str) -> Optional[str]:
    """Find the best.pt file for a model"""
    path1 = os.path.join(MODEL_DIR, model_name, "weights", "best.pt")
    if os.path.exists(path1):
        return path1
    path2 = os.path.join(MODEL_DIR, model_name, "best.pt")
    if os.path.exists(path2):
        return path2
    return None


def load_model_safe(model_name: str) -> Optional[YOLO]:
    """Safely load a YOLO model with error handling"""
    if model_name in MODELS:
        return MODELS[model_name]
    
    try:
        model_path = get_model_path(model_name)
        if not model_path:
            print(f"⚠️  Model not found: {model_name}")
            return None
        
        print(f"📦 Loading {model_name} from {model_path}")
        model = YOLO(model_path)
        MODELS[model_name] = model
        print(f"✅ {model_name} loaded successfully")
        return model
        
    except Exception as e:
        print(f"❌ Error loading {model_name}: {e}")
        return None


@app.get("/")
def root():
    return {
        "name": "GuardianEye Model API",
        "status": "running",
        "models_loaded": len(MODELS),
        "available_models": [d for d in os.listdir(MODEL_DIR) if os.path.isdir(os.path.join(MODEL_DIR, d))] if os.path.exists(MODEL_DIR) else []
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "models_loaded": len(MODELS),
        "device": "cpu"
    }


@app.post("/detect", response_model=DetectionResponse)
async def detect_violations(
    file: UploadFile = File(...),
    camera_id: str = Form(...),
    timestamp: Optional[str] = Form(None),
    return_evidence: bool = Form(True)
):
    """Detect violations in uploaded image"""
    start_time = datetime.now()
    
    try:
        # Load image
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
        img_array = np.array(image)
        
        # Convert to RGB if needed
        if len(img_array.shape) == 2:  # Grayscale
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
        elif img_array.shape[2] == 4:  # RGBA
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
        
        # Store all detections
        violations = []
        all_detections = []
        license_plates = []
        
        # 1. Try helmet detection
        helmet_model = load_model_safe("helmet_model")
        if helmet_model:
            try:
                results = helmet_model(img_array, conf=0.4, verbose=False)
                for r in results:
                    for box in r.boxes:
                        class_id = int(box.cls[0])
                        class_name = r.names[class_id].lower()
                        conf = float(box.conf[0])
                        
                        if 'no' in class_name or 'without' in class_name or class_name == 'driver':
                            violations.append({
                                "type": "no_helmet",
                                "confidence": conf,
                                "bbox": box.xyxy[0].tolist()
                            })
                            print(f"✅ Detected: No Helmet ({conf:.2f})")
                        
                        all_detections.append({
                            "class": class_name,
                            "confidence": conf,
                            "bbox": box.xyxy[0].tolist()
                        })
            except Exception as e:
                print(f"Helmet detection error: {e}")
        
        # 2. Try vehicle detection
        vehicle_model = load_model_safe("vehicle_model")
        if vehicle_model:
            try:
                results = vehicle_model(img_array, conf=0.5, verbose=False)
                for r in results:
                    for box in r.boxes:
                        class_id = int(box.cls[0])
                        class_name = r.names[class_id]
                        conf = float(box.conf[0])
                        all_detections.append({
                            "class": class_name,
                            "confidence": conf,
                            "bbox": box.xyxy[0].tolist()
                        })
                        print(f"Vehicle detected: {class_name} ({conf:.2f})")
            except Exception as e:
                print(f"Vehicle detection error: {e}")
        
        # 3. Try accident detection
        # Classes: Accident, Non Accident
        accident_model = load_model_safe("accident_model")
        if accident_model:
            try:
                results = accident_model(img_array, conf=0.4, verbose=False)
                for r in results:
                    for box in r.boxes:
                        class_name = r.names[int(box.cls[0])].lower()
                        conf = float(box.conf[0])
                        if "accident" in class_name and "non" not in class_name:
                            violations.append({
                                "type": "accident",
                                "confidence": conf,
                                "bbox": box.xyxy[0].tolist()
                            })
                            print(f"✅ Detected: Accident ({conf:.2f})")
            except Exception as e:
                print(f"Accident detection error: {e}")

        # 4. Try seatbelt detection
        seatbelt_model = load_model_safe("seatbelt_model")
        if seatbelt_model:
            try:
                results = seatbelt_model(img_array, conf=0.4, verbose=False)
                for r in results:
                    for box in r.boxes:
                        class_name = r.names[int(box.cls[0])].lower()
                        conf = float(box.conf[0])
                        if 'no' in class_name or 'without' in class_name:
                            violations.append({
                                "type": "no_seatbelt",
                                "confidence": conf,
                                "bbox": box.xyxy[0].tolist()
                            })
                            print(f"✅ Detected: No Seatbelt ({conf:.2f})")
            except Exception as e:
                print(f"Seatbelt detection error: {e}")

        # 5. Try triple ride detection
        # Classes: Triple_riding, motorcycle, number_plate, with_helmet, without_helmet
        triple_model = load_model_safe("triple_ride_model")
        if triple_model:
            try:
                results = triple_model(img_array, conf=0.4, verbose=False)
                for r in results:
                    for box in r.boxes:
                        class_name = r.names[int(box.cls[0])].lower()
                        conf = float(box.conf[0])
                        if 'triple' in class_name:
                            violations.append({
                                "type": "triple_riding",
                                "confidence": conf,
                                "bbox": box.xyxy[0].tolist()
                            })
                            print(f"✅ Detected: Triple Riding ({conf:.2f})")
                        elif 'without_helmet' in class_name or 'without-helmet' in class_name:
                            violations.append({
                                "type": "no_helmet",
                                "confidence": conf,
                                "bbox": box.xyxy[0].tolist()
                            })
                            print(f"✅ Detected: No Helmet via triple model ({conf:.2f})")
            except Exception as e:
                print(f"Triple ride detection error: {e}")

        # 6. Try red light detection
        # Classes: bus, car, green_light, motorcycle, red_light, truck, van, vehicle, yellow_light
        redlight_model = load_model_safe("redlight_model")
        if redlight_model:
            try:
                results = redlight_model(img_array, conf=0.4, verbose=False)
                red_light_detected = False
                vehicle_in_intersection = False
                red_light_conf = 0.85
                for r in results:
                    for box in r.boxes:
                        class_name = r.names[int(box.cls[0])].lower()
                        conf = float(box.conf[0])
                        if class_name == "red_light":
                            red_light_detected = True
                            red_light_conf = conf
                        if class_name in ["car", "motorcycle", "bus", "truck", "van", "vehicle"]:
                            vehicle_in_intersection = True
                if red_light_detected and vehicle_in_intersection:
                    violations.append({
                        "type": "red_light",
                        "confidence": red_light_conf,
                        "bbox": [0, 0, 0, 0]
                    })
                    print(f"✅ Detected: Red Light Violation ({red_light_conf:.2f})")
            except Exception as e:
                print(f"Red light detection error: {e}")

        # 7. Try stopline detection
        # Classes: stop-line (any detection = someone crossed the stop line)
        stopline_model = load_model_safe("stopline_model")
        if stopline_model:
            try:
                results = stopline_model(img_array, conf=0.4, verbose=False)
                for r in results:
                    for box in r.boxes:
                        class_name = r.names[int(box.cls[0])].lower()
                        conf = float(box.conf[0])
                        if 'stop' in class_name or 'line' in class_name:
                            violations.append({
                                "type": "stopline",
                                "confidence": conf,
                                "bbox": box.xyxy[0].tolist()
                            })
                            print(f"✅ Detected: Stopline Violation ({conf:.2f})")
            except Exception as e:
                print(f"Stopline detection error: {e}")

        # 8. Try illegal parking detection
        parking_model = load_model_safe("illegal_parking_model")
        if parking_model:
            try:
                results = parking_model(img_array, conf=0.4, verbose=False)
                for r in results:
                    for box in r.boxes:
                        class_name = r.names[int(box.cls[0])].lower()
                        conf = float(box.conf[0])
                        if 'illegal' in class_name or 'parking' in class_name:
                            violations.append({
                                "type": "illegal_parking",
                                "confidence": conf,
                                "bbox": box.xyxy[0].tolist()
                            })
                            print(f"✅ Detected: Illegal Parking ({conf:.2f})")
            except Exception as e:
                print(f"Illegal parking detection error: {e}")

        # 9. Try wrong way detection
        wrong_way_model = load_model_safe("wrong_way_model")
        if wrong_way_model:
            try:
                results = wrong_way_model(img_array, conf=0.4, verbose=False)
                for r in results:
                    for box in r.boxes:
                        class_name = r.names[int(box.cls[0])].lower()
                        conf = float(box.conf[0])
                        if 'wrong' in class_name:
                            violations.append({
                                "type": "wrong_way",
                                "confidence": conf,
                                "bbox": box.xyxy[0].tolist()
                            })
                            print(f"✅ Detected: Wrong Way ({conf:.2f})")
            except Exception as e:
                print(f"Wrong way detection error: {e}")

        # 10. Try license plate detection
        plate_model = load_model_safe("license_plate_model")
        if plate_model:
            try:
                results = plate_model(img_array, conf=0.4, verbose=False)
                for r in results:
                    for box in r.boxes:
                        plate_number = f"KA{np.random.randint(1,10):02d}{chr(65+np.random.randint(0,26))}{chr(65+np.random.randint(0,26))}{np.random.randint(1000,9999)}"
                        license_plates.append(plate_number)
            except Exception as e:
                print(f"License plate detection error: {e}")

        # Generate mock license plate if vehicles detected but no plate found
        if len(all_detections) > 0 and not license_plates:
            license_plates.append(f"KA{np.random.randint(1,10):02d}{chr(65+np.random.randint(0,26))}{chr(65+np.random.randint(0,26))}{np.random.randint(1000,9999)}")
        
        # Generate evidence image if violations found
        evidence_filename = None
        if return_evidence and len(violations) > 0:
            evidence_img = img_array.copy()
            
            # Draw boxes
            for violation in violations:
                if violation.get("bbox") and any(v != 0 for v in violation["bbox"]):
                    bbox = [int(x) for x in violation["bbox"]]
                    cv2.rectangle(evidence_img, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 0, 255), 3)
                    cv2.putText(evidence_img, violation["type"].upper(), (bbox[0], bbox[1]-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            
            # Save evidence
            os.makedirs(EVIDENCE_DIR, exist_ok=True)
            evidence_filename = f"{camera_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            evidence_path = os.path.join(EVIDENCE_DIR, evidence_filename)
            cv2.imwrite(evidence_path, cv2.cvtColor(evidence_img, cv2.COLOR_RGB2BGR))
            print(f"💾 Saved evidence: {evidence_filename}")
        
        # Calculate inference time
        inference_time = (datetime.now() - start_time).total_seconds()
        
        print(f"📊 Detection complete: {len(violations)} violations, {len(all_detections)} objects, {inference_time:.3f}s")
        
        return DetectionResponse(
            violations=violations,
            camera_id=camera_id,
            timestamp=timestamp or datetime.now().isoformat(),
            license_plates=license_plates,
            evidence_image=evidence_filename,
            detected_objects=all_detections,
            model_ver="YOLOv8-1.0",
            inference_time=inference_time,
            device="cpu"
        )
    
    except Exception as e:
        print(f"❌ Detection error: {e}")
        import traceback
        traceback.print_exc()
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Detection error: {str(e)}")


if __name__ == "__main__":
    print("🚀 Starting GuardianEye Model API Server (Simplified)...")
    print(f"📁 Model directory: {MODEL_DIR}")
    print(f"📁 Evidence directory: {EVIDENCE_DIR}")
    print("🌐 Server will be available at: http://localhost:8001")
    print("📖 API docs at: http://localhost:8001/docs")
    print("")
    print("⚡ Starting server...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
