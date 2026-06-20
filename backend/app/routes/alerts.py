from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..database import get_database
from ..models.schemas import AlertType, AlertStatus
from ..services.alert_service import AlertService
from ..services.incident_service import IncidentService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("/send-police", response_model=dict)
async def send_police_alert(
    incident_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Send alert to police for an incident
    
    - **incident_id**: The incident ID to send alert for
    """
    incident_service = IncidentService(db)
    incident = await incident_service.get_incident_by_id(incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    alert_service = AlertService(db)
    alert = await alert_service.create_alert(
        incident=incident,
        alert_type=AlertType.POLICE,
        recipient="Delhi Traffic Police"
    )
    
    return {
        "success": True,
        "message": "Police alert sent successfully",
        "alert_id": alert["alert_id"],
        "data": alert
    }


@router.post("/send-hospital", response_model=dict)
async def send_hospital_alert(
    incident_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Send alert to hospital for an accident
    
    - **incident_id**: The incident ID (should be an accident)
    """
    incident_service = IncidentService(db)
    incident = await incident_service.get_incident_by_id(incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    alert_service = AlertService(db)
    
    # Send to both hospital and ambulance
    hospital_alert = await alert_service.create_alert(
        incident=incident,
        alert_type=AlertType.HOSPITAL,
        recipient="AIIMS Delhi Emergency"
    )
    
    ambulance_alert = await alert_service.create_alert(
        incident=incident,
        alert_type=AlertType.AMBULANCE,
        recipient="108 Ambulance Service"
    )
    
    return {
        "success": True,
        "message": "Hospital and ambulance alerts sent successfully",
        "alerts": [hospital_alert, ambulance_alert]
    }


@router.get("/", response_model=dict)
async def get_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    alert_type: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get all alerts with optional filters
    
    - **alert_type**: Filter by type (police, hospital, ambulance)
    - **status**: Filter by status (sent, acknowledged, dispatched, completed)
    - **severity**: Filter by severity (low, medium, high, critical)
    """
    alert_service = AlertService(db)
    alerts = await alert_service.get_all_alerts(
        skip=skip,
        limit=limit,
        alert_type=alert_type,
        status=status,
        severity=severity
    )
    return {"alerts": alerts, "total": len(alerts)}


# ── Static sub-paths BEFORE /{alert_id} ──────────────────────────────────────

@router.get("/stats/pending", response_model=dict)
async def get_pending_alerts(
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get count of pending alerts"""
    alert_service = AlertService(db)
    count = await alert_service.get_pending_alerts()
    return {"pending_alerts": count}


# ── Parameterized routes LAST ─────────────────────────────────────────────────

@router.get("/{alert_id}", response_model=dict)
async def get_alert(
    alert_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get single alert by ID"""
    alert_service = AlertService(db)
    alert = await alert_service.get_alert_by_id(alert_id)
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return alert


@router.patch("/{alert_id}/status", response_model=dict)
async def update_alert_status(
    alert_id: str,
    status: AlertStatus,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Update alert status
    
    - **status**: New status (sent, acknowledged, dispatched, completed)
    """
    alert_service = AlertService(db)
    alert = await alert_service.update_alert_status(alert_id, status)
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {
        "success": True,
        "message": f"Alert status updated to {status.value}",
        "data": alert
    }
