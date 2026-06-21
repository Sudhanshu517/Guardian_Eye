"""
Processing Routes - Image Upload and AI Processing

This module handles:
1. Image upload from cameras
2. Sending images to AI model
3. Processing model output
4. Creating incidents automatically
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
import os
import asyncio
from datetime import datetime
import uuid
from ..database import get_database
from ..services.model_service import get_model_service
from ..services.incident_service import IncidentService
from ..config import settings
from ..models.schemas import DetectionInput, ViolationSchema

router = APIRouter(prefix="/api/process", tags=["processing"])


# ── Violation scoring map ─────────────────────────────────────────────────────
VIOLATION_SCORES = {
    "accident":        50,
    "wrong_way":       45,
    "red_light":       40,
    "no_helmet":       30,
    "no_seatbelt":     25,
    "triple_riding":   20,
    "stopline":        15,
    "illegal_parking": 10,
}

VIOLATION_SEVERITY = {
    "accident":        "critical",
    "wrong_way":       "critical",
    "red_light":       "high",
    "no_helmet":       "high",
    "no_seatbelt":     "medium",
    "triple_riding":   "medium",
    "stopline":        "medium",
    "illegal_parking": "low",
}


def _build_detection_input(model_output: dict, location_name: str) -> DetectionInput:
    """
    Map raw YOLO model output → DetectionInput schema.

    model_output structure (from model API /detect):
        violations: [{type, confidence, bbox}, ...]
        camera_id: str
        timestamp: str
        license_plates: [str, ...]
        evidence_image: str | None
        detected_objects: [{class, confidence, bbox}, ...]
    """
    raw_violations = model_output.get("violations", [])
    timestamp_str = model_output.get("timestamp", datetime.utcnow().isoformat())

    # Build ViolationSchema list
    violation_schemas = []
    for v in raw_violations:
        vtype = v.get("type", "unknown")
        conf = float(v.get("confidence", 0.0))
        score = VIOLATION_SCORES.get(vtype, 10)
        severity = VIOLATION_SEVERITY.get(vtype, "medium")
        violation_schemas.append(
            ViolationSchema(
                type=vtype,
                class_name=vtype,
                confidence=conf,
                score=score,
                severity=severity,
                time=timestamp_str,
            )
        )

    # Compute aggregate score and severity
    total_score = sum(VIOLATION_SCORES.get(v.get("type", ""), 10) for v in raw_violations)

    critical_types = {"accident", "wrong_way", "red_light"}
    if any(v.get("type") in critical_types for v in raw_violations):
        overall_severity = "🔴 CRITICAL"
    elif total_score >= 25:
        overall_severity = "🟠 HIGH"
    elif total_score >= 10:
        overall_severity = "🟡 MEDIUM"
    else:
        overall_severity = "🟢 LOW"

    return DetectionInput(
        timestamp=timestamp_str,
        camera_id=model_output.get("camera_id", "UNKNOWN"),
        location=location_name,
        total_score=total_score,
        overall_severity=overall_severity,
        violations=violation_schemas,
        license_plates=model_output.get("license_plates", []),
        image=model_output.get("evidence_image"),
        cloudinary_url=model_output.get("cloudinary_url"),
        cloudinary_public_id=model_output.get("cloudinary_public_id"),
        alert_sent=False,
    )


@router.post("/upload", response_model=dict)
async def upload_and_process(
    file: UploadFile = File(..., description="Image file from camera"),
    camera_id: str = Form(..., description="Camera ID"),
    location: Optional[str] = Form(None, description="Location name"),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Upload image from camera and process it through AI model

    **Complete Pipeline:**
    1. Receive image from camera
    2. Save image to uploads directory
    3. Send to AI model for processing
    4. Receive violation detection results
    5. Create incident in database
    6. Trigger alerts if needed

    **Usage:**
    ```bash
    curl -X POST http://localhost:8000/api/process/upload \\
      -F "file=@camera_image.jpg" \\
      -F "camera_id=CAM-001" \\
      -F "location=Silk Board Junction"
    ```
    """
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail="File must be an image (JPEG, PNG, etc.)"
        )

    print(f"\n📥 [upload] Request received: camera_id={camera_id}, file={file.filename}, content_type={file.content_type}")

    try:
        # Generate unique filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_extension = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
        unique_filename = f"{camera_id}_{timestamp}_{uuid.uuid4().hex[:8]}{file_extension}"

        # Save uploaded file
        upload_dir = os.path.join(settings.base_dir, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, unique_filename)

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        print(f"💾 [upload] File saved: {file_path} ({len(content):,} bytes)")

        location_name = location or "Unknown Location"

        # Send to model for processing
        model_service = get_model_service()

        try:
            print(f"🤖 [upload] AI processing started …")
            model_output = await asyncio.wait_for(
                model_service.detect_violations(
                    image_path=file_path,
                    camera_id=camera_id,
                    timestamp=datetime.utcnow().isoformat()
                ),
                timeout=120.0  # 2-minute hard limit (cold YOLO model load can be slow)
            )
            print(f"✅ [upload] AI processing complete — {len(model_output.get('violations', []))} violation(s) found")

            # Check if violations were detected
            raw_violations = model_output.get("violations", [])
            if not raw_violations:
                print("ℹ️  [upload] No violations detected — returning early")
                return {
                    "success": True,
                    "message": "No violations detected",
                    "violations_detected": 0,
                    "image_path": file_path
                }

            # Map model output → DetectionInput
            detection_input = _build_detection_input(model_output, location_name)

            # Create incident in DB
            print(f"🗄️  [upload] Saving incident to database …")
            incident_service = IncidentService(db)
            incident = await incident_service.create_from_detection(detection_input)
            print(f"✅ [upload] Incident created: {incident.get('incident_id')}")

            primary = incident.get("violation_type", raw_violations[0].get("type", "unknown"))

            response_payload = {
                "success": True,
                "message": "Image processed and incident created",
                "incident_id": incident["incident_id"],
                "violations_detected": len(raw_violations),
                "primary_violation": primary,
                "severity": incident.get("severity"),
                "confidence": incident.get("confidence"),
                "incident": incident,
            }
            print(f"📤 [upload] Response ready — returning to client")
            return response_payload

        except asyncio.TimeoutError:
            print(f"⏰ [upload] AI processing timed out after 120s")
            return {
                "success": False,
                "message": "AI processing timed out (models may still be loading). Please retry.",
                "image_saved": file_path,
                "note": "Image saved; retry in a few seconds once models are warm."
            }

        except Exception as model_error:
            # Model processing failed – save image for manual review
            print(f"❌ [upload] Model error: {model_error}")
            return {
                "success": False,
                "message": f"Model processing error: {str(model_error)}",
                "image_saved": file_path,
                "note": "Image saved for manual review"
            }

    except Exception as e:
        print(f"❌ [upload] Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing upload: {str(e)}"
        )


@router.post("/upload-batch", response_model=dict)
async def upload_and_process_batch(
    files: List[UploadFile] = File(..., description="Multiple image files"),
    camera_ids: List[str] = Form(..., description="Camera IDs (comma-separated)"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Upload and process multiple images in batch

    Useful for:
    - Processing queued camera captures
    - Bulk historical data processing
    - Testing with multiple samples
    """
    results = []

    for file, camera_id in zip(files, camera_ids):
        try:
            result = await upload_and_process(
                file=file,
                camera_id=camera_id,
                db=db
            )
            results.append(result)
        except Exception as e:
            results.append({
                "success": False,
                "error": str(e),
                "file": file.filename
            })

    successful = sum(1 for r in results if r.get("success"))

    return {
        "total_processed": len(files),
        "successful": successful,
        "failed": len(files) - successful,
        "results": results
    }


@router.get("/model-health", response_model=dict)
async def check_model_health():
    """
    Check if AI model service is reachable and healthy

    Use this to verify model integration before processing images
    """
    model_service = get_model_service()
    health = await model_service.health_check()

    if health["status"] != "healthy":
        raise HTTPException(
            status_code=503,
            detail=f"Model service unavailable: {health.get('error')}"
        )

    return health


@router.post("/simulate", response_model=dict)
async def simulate_detection(
    camera_id: str = Form(...),
    violation_type: str = Form(...),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Simulate a violation detection without actual image

    Useful for:
    - Testing the system
    - Demo purposes
    - Development without running model

    **Example:**
    ```bash
    curl -X POST http://localhost:8000/api/process/simulate \\
      -F "camera_id=CAM-001" \\
      -F "violation_type=red_light"
    ```
    """
    score = VIOLATION_SCORES.get(violation_type, 10)
    severity = VIOLATION_SEVERITY.get(violation_type, "medium")
    ts = datetime.utcnow().isoformat()

    mock_detection = DetectionInput(
        timestamp=ts,
        camera_id=camera_id,
        location="Test Location - Simulated",
        total_score=score,
        overall_severity=f"🟠 {severity.upper()}",
        violations=[
            ViolationSchema(
                type=violation_type,
                class_name=violation_type,
                confidence=0.85,
                score=score,
                severity=severity,
                time=ts,
            )
        ],
        license_plates=["KA01AB1234"],
        image=f"simulated_{violation_type}.jpg",
        alert_sent=False,
    )

    incident_service = IncidentService(db)
    incident = await incident_service.create_from_detection(mock_detection)

    return {
        "success": True,
        "message": "Simulated detection created",
        "mode": "simulation",
        "incident_id": incident["incident_id"],
        "incident": incident
    }
