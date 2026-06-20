from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..database import get_database
from ..models.schemas import (
    DetectionInput, IncidentUpdateStatus,
    IncidentStatus
)
from ..services.incident_service import IncidentService

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.post("/", response_model=dict)
async def create_incident(
    detection: DetectionInput,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Create incident from AI model detection output
    
    This endpoint receives the JSON output from the AI model
    and processes it into an incident record.
    """
    service = IncidentService(db)
    incident = await service.create_from_detection(detection)
    return {
        "success": True,
        "message": "Incident created successfully",
        "incident_id": incident["incident_id"],
        "data": incident
    }


@router.get("/", response_model=dict)
async def get_incidents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    severity: Optional[str] = None,
    status: Optional[str] = None,
    camera_id: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get all incidents with optional filters
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **severity**: Filter by severity (low, medium, high, critical)
    - **status**: Filter by status (new, alert_sent, in_review, resolved)
    - **camera_id**: Filter by camera ID
    """
    service = IncidentService(db)
    incidents = await service.get_all_incidents(
        skip=skip,
        limit=limit,
        severity=severity,
        status=status,
        camera_id=camera_id
    )
    return {"incidents": incidents, "total": len(incidents)}


# ── All /stats/* and other static sub-paths MUST come BEFORE /{incident_id} ──

@router.get("/recent", response_model=dict)
async def get_recent_incidents(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get recent incidents within last N hours
    
    - **hours**: Look back period in hours (default: 24)
    - **limit**: Maximum number of incidents to return
    """
    service = IncidentService(db)
    incidents = await service.get_recent_incidents(hours=hours, limit=limit)
    return {"incidents": incidents, "total": len(incidents)}


@router.get("/stats/violations-today", response_model=dict)
async def get_violations_today(
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get total violations count for today"""
    service = IncidentService(db)
    count = await service.get_violations_today()
    return {"violations_today": count}


@router.get("/stats/trend", response_model=dict)
async def get_violation_trend(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get violation trend for last N hours
    
    Returns hourly violation counts
    """
    service = IncidentService(db)
    trend = await service.get_violation_trend(hours=hours)
    return {"trend": trend}


@router.get("/stats/top-violations", response_model=dict)
async def get_top_violations(
    limit: int = Query(5, ge=1, le=20),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get top violation types by count"""
    service = IncidentService(db)
    top = await service.get_top_violations(limit=limit)
    return {"violations": top}


# ── Parameterized routes LAST ─────────────────────────────────────────────────

@router.get("/{incident_id}", response_model=dict)
async def get_incident(
    incident_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get single incident by ID
    
    - **incident_id**: The incident ID (e.g., INC-20260618-1234)
    """
    service = IncidentService(db)
    incident = await service.get_incident_by_id(incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    return incident


@router.patch("/{incident_id}/status", response_model=dict)
async def update_incident_status(
    incident_id: str,
    status_update: IncidentUpdateStatus,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Update incident status
    
    - **incident_id**: The incident ID
    - **status**: New status (new, alert_sent, in_review, acknowledged, dispatched, resolved)
    """
    service = IncidentService(db)
    incident = await service.update_incident_status(incident_id, status_update.status)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    return {
        "success": True,
        "message": f"Incident status updated to {status_update.status.value}",
        "data": incident
    }
