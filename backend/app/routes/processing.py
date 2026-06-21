"""
Processing Routes - Image Upload and AI Processing

Pipeline:
1. Receive image bytes from frontend (no local file saved)
2. Run YOLO inference in-process (from bytes)
3. Evidence image written to tempfile → uploaded to Cloudinary → tempfile deleted
4. Create a new incident OR append evidence to an existing one (video multi-frame)
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
import asyncio
from datetime import datetime
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
    """Map raw YOLO model output → DetectionInput schema."""
    raw_violations = model_output.get("violations", [])
    timestamp_str = model_output.get("timestamp", datetime.utcnow().isoformat())

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
        image=None,                                         # no local file
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
    # Optional: attach this frame to an existing incident (video multi-frame)
    incident_id: Optional[str] = Form(None, description="Existing incident ID to append evidence to"),
    # Optional: timestamp of this frame within the video (seconds)
    timestamp_in_video: Optional[float] = Form(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Upload image/frame from camera and process it through AI model.

    **Complete Pipeline:**
    1. Read image bytes into memory (no local save)
    2. Run YOLO inference in-process
    3. Evidence drawn → tempfile → Cloudinary upload → tempfile deleted
    4. If `incident_id` provided → append evidence frame to existing incident
    5. Otherwise → create a new incident

    **Usage (single image):**
    ```bash
    curl -X POST http://localhost:8000/api/process/upload \\
      -F "file=@camera_image.jpg" \\
      -F "camera_id=CAM-001" \\
      -F "location=Silk Board Junction"
    ```

    **Usage (video frame, append to existing incident):**
    ```bash
    curl -X POST http://localhost:8000/api/process/upload \\
      -F "file=@frame_42.jpg" \\
      -F "camera_id=DEMO-VID" \\
      -F "incident_id=INC-20240621-001" \\
      -F "timestamp_in_video=21.0"
    ```
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (JPEG, PNG, etc.)")

    print(f"\n📥 [upload] camera_id={camera_id}, file={file.filename}, incident_id={incident_id}")

    try:
        content = await file.read()
        location_name = location or "Unknown Location"
        model_service = get_model_service()

        try:
            print("🤖 [upload] AI processing started …")
            model_output = await asyncio.wait_for(
                model_service.detect_violations_from_bytes(
                    image_bytes=content,
                    camera_id=camera_id,
                    timestamp=datetime.utcnow().isoformat(),
                ),
                timeout=120.0,
            )
            print(f"✅ [upload] AI done — {len(model_output.get('violations', []))} violation(s)")

            raw_violations = model_output.get("violations", [])
            cloudinary_url = model_output.get("cloudinary_url")
            cloudinary_public_id = model_output.get("cloudinary_public_id")

            if not raw_violations:
                print("ℹ️  [upload] No violations detected")
                return {
                    "success": True,
                    "message": "No violations detected",
                    "violations_detected": 0,
                    "incident_id": incident_id,  # return existing id (or None)
                }

            incident_service = IncidentService(db)

            # ── Video multi-frame: append to existing incident ────────────────
            if incident_id and cloudinary_url:
                print(f"📎 [upload] Appending evidence frame to incident {incident_id}")
                await incident_service.append_evidence(
                    incident_id=incident_id,
                    evidence_image={
                        "cloudinary_url": cloudinary_url,
                        "public_id": cloudinary_public_id,
                        "timestamp_in_video": timestamp_in_video,
                        "detected_at": datetime.utcnow().isoformat(),
                    },
                )
                primary = raw_violations[0].get("type", "unknown")
                return {
                    "success": True,
                    "message": "Evidence frame appended to existing incident",
                    "incident_id": incident_id,
                    "violations_detected": len(raw_violations),
                    "primary_violation": primary,
                    "cloudinary_url": cloudinary_url,
                }

            # ── New incident ──────────────────────────────────────────────────
            print("🗄️  [upload] Creating new incident …")
            detection_input = _build_detection_input(model_output, location_name)
            incident = await incident_service.create_from_detection(detection_input)

            # If we also have a Cloudinary URL from this frame, seed evidence_images
            if cloudinary_url:
                await incident_service.append_evidence(
                    incident_id=incident["incident_id"],
                    evidence_image={
                        "cloudinary_url": cloudinary_url,
                        "public_id": cloudinary_public_id,
                        "timestamp_in_video": timestamp_in_video,
                        "detected_at": datetime.utcnow().isoformat(),
                    },
                )

            print(f"✅ [upload] Incident created: {incident.get('incident_id')}")
            primary = incident.get("violation_type", raw_violations[0].get("type", "unknown"))

            return {
                "success": True,
                "message": "Image processed and incident created",
                "incident_id": incident["incident_id"],
                "violations_detected": len(raw_violations),
                "primary_violation": primary,
                "severity": incident.get("severity"),
                "confidence": incident.get("confidence"),
                "cloudinary_url": cloudinary_url,
                "incident": incident,
            }

        except asyncio.TimeoutError:
            print("⏰ [upload] AI timed out after 120 s")
            return {
                "success": False,
                "message": "AI processing timed out (models may still be loading). Please retry.",
                "note": "Retry in a few seconds once models are warm.",
            }

        except Exception as model_error:
            print(f"❌ [upload] Model error: {model_error}")
            return {
                "success": False,
                "message": f"Model processing error: {str(model_error)}",
            }

    except Exception as e:
        print(f"❌ [upload] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")


@router.post("/upload-batch", response_model=dict)
async def upload_and_process_batch(
    files: List[UploadFile] = File(..., description="Multiple image files"),
    camera_ids: List[str] = Form(..., description="Camera IDs (comma-separated)"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Upload and process multiple images in batch."""
    results = []
    for file, camera_id in zip(files, camera_ids):
        try:
            result = await upload_and_process(file=file, camera_id=camera_id, db=db)
            results.append(result)
        except Exception as e:
            results.append({"success": False, "error": str(e), "file": file.filename})

    successful = sum(1 for r in results if r.get("success"))
    return {
        "total_processed": len(files),
        "successful": successful,
        "failed": len(files) - successful,
        "results": results,
    }


@router.get("/model-health", response_model=dict)
async def check_model_health():
    """Check if AI model service is reachable and healthy."""
    model_service = get_model_service()
    health = await model_service.health_check()
    if health["status"] != "healthy":
        raise HTTPException(status_code=503, detail=f"Model service unavailable: {health.get('error')}")
    return health


@router.post("/simulate", response_model=dict)
async def simulate_detection(
    camera_id: str = Form(...),
    violation_type: str = Form(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Simulate a violation detection without actual image (for testing/demo)."""
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
        image=None,
        alert_sent=False,
    )

    incident_service = IncidentService(db)
    incident = await incident_service.create_from_detection(mock_detection)

    return {
        "success": True,
        "message": "Simulated detection created",
        "mode": "simulation",
        "incident_id": incident["incident_id"],
        "incident": incident,
    }
