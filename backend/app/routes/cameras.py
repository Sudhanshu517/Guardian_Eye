from fastapi import APIRouter, Depends, HTTPException
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..database import get_database

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("/", response_model=dict)
async def get_cameras(
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get all cameras"""
    cameras = db.cameras
    cursor = cameras.find({}).sort("camera_id", 1)
    cameras_list = await cursor.to_list(length=None)
    
    for cam in cameras_list:
        cam["_id"] = str(cam["_id"])
    
    return {"cameras": cameras_list, "total": len(cameras_list)}


@router.get("/{camera_id}", response_model=dict)
async def get_camera(
    camera_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get single camera by ID"""
    cameras = db.cameras
    camera = await cameras.find_one({"camera_id": camera_id})
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    camera["_id"] = str(camera["_id"])
    
    # Get detection count for this camera
    incidents = db.incidents
    detection_count = await incidents.count_documents({"camera_id": camera_id})
    camera["total_detections"] = detection_count
    
    return camera
