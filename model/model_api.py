"""
GuardianEye Model API Server

This creates a REST API endpoint for the YOLOv8 models
so the backend can send images and receive detections.

Run with: python model_api.py
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

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import base64
import io
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
import json

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

# Model paths
MODEL_DIR = "./models"
EVIDENCE_DIR = "./evidence"

# Load models (lazy loading)
MODELS = {}

def load_model(model_name: str):
    """Load a YOLO model if not already loaded"""
    if model_name not in MODELS:
        model_path = os.path.join(MODEL_DIR, model_name, "weights", "best.pt")
        if not os.path.exists(model_path):
            # Try alternative path
            model_path = os.path.join(MODEL_DIR, model_name, "best.pt")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        print(f"📦 Loading {model_name} from {model_path}")
        model = YOLO(model_path)
        MODELS[model_name] = model
        print(f"✅ {model_name} loaded successfully")
    return MODELS[model_name]


class DetectionRequest(BaseModel):
    image: str  # base64 encoded image
    camera_id: str
    timestamp: Optional[str] = None
    return_evidence: bool = True


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


@app.get("/")
def root():
    return {
        "name": "GuardianEye Model API",
        "status": "running",
        "models_loaded": list(MODELS.keys()),
        "available_models": os.listdir(MODEL_DIR) if os.path.exists(MODEL_DIR) else []
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
    """
    Detect violations in an image
    
    Accepts multipart/form-data with:
    - file: Image file (required)
    - camera_id: Camera ID (required)
    - timestamp: Optional timestamp
    - return_evidence: Whether to generate evidence image
    """
    start_time = datetime.now()
    
    try:
        # Load image from uploaded file
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to numpy array
        img_array = np.array(image)
        if len(img_array.shape) == 2:  # Grayscale
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
        elif img_array.shape[2] == 4:  # RGBA
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
        
        # Run detection with multiple models
        violations = []
        all_detections = []
        license_plates = []
        
        # 1. Vehicle detection (base model)
        try:
            vehicle_model = load_model("vehicle_model")
            vehicle_results = vehicle_model(img_array, conf=0.5, verbose=False)
            for r in vehicle_results:
                for box in r.boxes:
                    all_detections.append({
                        "class": r.names[int(box.cls)],
                        "confidence": float(box.conf),
                        "bbox": box.xyxy[0].tolist()
                    })
        except Exception as e:
            print(f"Vehicle detection error: {e}")
        
        # 2. Helmet detection
        try:
            helmet_model = load_model("helmet_model")
            helmet_results = helmet_model(img_array, conf=0.4, verbose=False)
            for r in helmet_results:
                for box in r.boxes:
                    class_name = r.names[int(box.cls)]
                    conf = float(box.conf)
                    if 'no' in class_name.lower() or 'without' in class_name.lower() or class_name.lower() == 'driver':
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
        
        # 3. Red light detection
        # Classes: bus, car, green_light, motorcycle, red_light, truck, van, vehicle, yellow_light
        try:
            redlight_model = load_model("redlight_model")
            redlight_results = redlight_model(img_array, conf=0.4, verbose=False)
            red_light_detected = False
            vehicle_in_intersection = False
            red_light_conf = 0.85
            
            for r in redlight_results:
                for box in r.boxes:
                    class_name = r.names[int(box.cls)].lower()
                    conf = float(box.conf)
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
                print(f"✅ Detected: Red Light violation ({red_light_conf:.2f})")
        except Exception as e:
            print(f"Red light detection error: {e}")
        
        # 4. Wrong way detection
        try:
            wrong_way_model = load_model("wrong_way_model")
            wrong_way_results = wrong_way_model(img_array, conf=0.5, verbose=False)
            for r in wrong_way_results:
                for box in r.boxes:
                    class_name = r.names[int(box.cls)]
                    conf = float(box.conf)
                    if "wrong" in class_name.lower():
                        violations.append({
                            "type": "wrong_way",
                            "confidence": conf,
                            "bbox": box.xyxy[0].tolist()
                        })
                        print(f"✅ Detected: Wrong way ({conf:.2f})")
        except Exception as e:
            print(f"Wrong way detection error: {e}")
        
        # 5. Accident detection
        # Classes: Accident, Non Accident
        try:
            accident_model = load_model("accident_model")
            accident_results = accident_model(img_array, conf=0.4, verbose=False)
            for r in accident_results:
                for box in r.boxes:
                    class_name = r.names[int(box.cls)].lower()
                    conf = float(box.conf)
                    if "accident" in class_name and "non" not in class_name:
                        violations.append({
                            "type": "accident",
                            "confidence": conf,
                            "bbox": box.xyxy[0].tolist()
                        })
                        print(f"✅ Detected: Accident ({conf:.2f})")
        except Exception as e:
            print(f"Accident detection error: {e}")
        
        # 6. Seatbelt detection
        try:
            seatbelt_model = load_model("seatbelt_model")
            seatbelt_results = seatbelt_model(img_array, conf=0.4, verbose=False)
            for r in seatbelt_results:
                for box in r.boxes:
                    class_name = r.names[int(box.cls)]
                    conf = float(box.conf)
                    if 'no' in class_name.lower() or 'without' in class_name.lower():
                        violations.append({
                            "type": "no_seatbelt",
                            "confidence": conf,
                            "bbox": box.xyxy[0].tolist()
                        })
                        print(f"✅ Detected: No Seatbelt ({conf:.2f})")
        except Exception as e:
            print(f"Seatbelt detection error: {e}")

        # 7. Triple ride detection
        # Classes: Triple_riding, motorcycle, number_plate, with_helmet, without_helmet
        try:
            triple_model = load_model("triple_ride_model")
            triple_results = triple_model(img_array, conf=0.4, verbose=False)
            for r in triple_results:
                for box in r.boxes:
                    class_name = r.names[int(box.cls)].lower()
                    conf = float(box.conf)
                    if "triple" in class_name:
                        violations.append({
                            "type": "triple_riding",
                            "confidence": conf,
                            "bbox": box.xyxy[0].tolist()
                        })
                        print(f"✅ Detected: Triple Riding ({conf:.2f})")
                    elif "without_helmet" in class_name or "without-helmet" in class_name:
                        # Also catch no-helmet from triple ride model
                        violations.append({
                            "type": "no_helmet",
                            "confidence": conf,
                            "bbox": box.xyxy[0].tolist()
                        })
                        print(f"✅ Detected: No Helmet via triple model ({conf:.2f})")
        except Exception as e:
            print(f"Triple ride detection error: {e}")

        # 8. Stopline detection
        # Classes: stop-line (any detection = someone crossed the line)
        try:
            stopline_model = load_model("stopline_model")
            stopline_results = stopline_model(img_array, conf=0.4, verbose=False)
            for r in stopline_results:
                for box in r.boxes:
                    class_name = r.names[int(box.cls)].lower()
                    conf = float(box.conf)
                    if "stop" in class_name or "line" in class_name:
                        violations.append({
                            "type": "stopline",
                            "confidence": conf,
                            "bbox": box.xyxy[0].tolist()
                        })
                        print(f"✅ Detected: Stopline Violation ({conf:.2f})")
        except Exception as e:
            print(f"Stopline detection error: {e}")

        # 9. Illegal parking detection
        try:
            parking_model = load_model("illegal_parking_model")
            parking_results = parking_model(img_array, conf=0.4, verbose=False)
            for r in parking_results:
                for box in r.boxes:
                    class_name = r.names[int(box.cls)]
                    conf = float(box.conf)
                    if 'illegal' in class_name.lower() or 'parking' in class_name.lower():
                        violations.append({
                            "type": "illegal_parking",
                            "confidence": conf,
                            "bbox": box.xyxy[0].tolist()
                        })
                        print(f"✅ Detected: Illegal parking ({conf:.2f})")
        except Exception as e:
            print(f"Illegal parking detection error: {e}")
        
        # 10. License plate detection and mock OCR
        try:
            plate_model = load_model("license_plate_model")
            plate_results = plate_model(img_array, conf=0.4, verbose=False)
            for r in plate_results:
                for box in r.boxes:
                    plate_number = f"KA{np.random.randint(1,10):02d}{chr(65+np.random.randint(0,26))}{chr(65+np.random.randint(0,26))}{np.random.randint(1000,9999)}"
                    license_plates.append(plate_number)
        except Exception as e:
            print(f"License plate detection error: {e}")
        
        # Auto-generate a mock plate if vehicles were found but no plate model succeeded
        if len(all_detections) > 0 and not license_plates:
            license_plates.append(f"KA{np.random.randint(1,10):02d}{chr(65+np.random.randint(0,26))}{chr(65+np.random.randint(0,26))}{np.random.randint(1000,9999)}")

        # Generate evidence image
        evidence_filename = None
        if return_evidence and violations:
            evidence_img = img_array.copy()
            
            # Draw bounding boxes for violations
            for violation in violations:
                if violation.get("bbox") and any(v != 0 for v in violation["bbox"]):
                    bbox = [int(x) for x in violation["bbox"]]
                    cv2.rectangle(evidence_img, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 0, 255), 2)
                    cv2.putText(evidence_img, violation["type"], (bbox[0], bbox[1]-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
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
        raise HTTPException(status_code=500, detail=f"Detection error: {str(e)}")


@app.post("/detect-simple")
async def detect_simple(file: UploadFile = File(...)):
    """
    Simplified detection endpoint that just returns violations.
    Good for quick testing.
    """
    try:
        result = await detect_violations(
            file=file,
            camera_id="TEST",
            return_evidence=False
        )
        return {
            "violations_detected": len(result.violations),
            "violations": result.violations,
            "inference_time": result.inference_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print("🚀 Starting GuardianEye Model API Server...")
    print(f"📁 Model directory: {MODEL_DIR}")
    print(f"📁 Evidence directory: {EVIDENCE_DIR}")
    print("🌐 Server will be available at: http://localhost:8001")
    print("📖 API docs at: http://localhost:8001/docs")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
