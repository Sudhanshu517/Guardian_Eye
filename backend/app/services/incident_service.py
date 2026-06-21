from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from ..models.schemas import (
    DetectionInput, IncidentCreate, IncidentResponse,
    SeverityLevel, IncidentStatus, LocationSchema
)
from ..utils.helpers import (
    generate_id, calculate_severity, parse_severity_emoji,
    get_violation_type, format_timestamp, mock_location_coordinates
)


class IncidentService:
    """Service for incident management"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.incidents
    
    async def create_from_detection(self, detection: DetectionInput) -> Dict[str, Any]:
        """Create incident from AI model detection"""
        
        # Parse location
        coords = mock_location_coordinates(detection.location)
        location = LocationSchema(
            name=detection.location,
            lat=coords["lat"],
            lng=coords["lng"]
        )
        
        # Calculate severity
        violations_list = [v.model_dump() for v in detection.violations]
        severity_str = parse_severity_emoji(detection.overall_severity)
        
        # Get primary violation type
        primary_violation = get_violation_type(violations_list)
        
        # Calculate average confidence
        confidences = [v.confidence for v in detection.violations if v.confidence]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Create incident document
        incident_doc = {
            "incident_id": generate_id("INC"),
            "camera_id": detection.camera_id,
            "timestamp": format_timestamp(detection.timestamp),
            "location": location.model_dump(),
            "violation_type": primary_violation,
            "severity": severity_str,
            "total_score": detection.total_score,
            "confidence": round(avg_confidence, 2),
            "license_plates": detection.license_plates,
            "violations": violations_list,
            "evidence_image": detection.image,
            "cloudinary_url": detection.cloudinary_url,
            "cloudinary_public_id": detection.cloudinary_public_id,
            "peak_hour": detection.peak_hour,
            "weather": detection.weather,
            "status": IncidentStatus.NEW.value,
            "alert_sent": detection.alert_sent,
            "alerts": [],
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        
        # Insert into database
        result = await self.collection.insert_one(incident_doc)
        incident_doc["_id"] = str(result.inserted_id)
        
        # Update offender tracking if license plate exists
        if detection.license_plates:
            for plate in detection.license_plates:
                await self._update_offender(plate, primary_violation)
        
        # Update camera last seen
        await self._update_camera(detection.camera_id, detection.location, coords)
        
        return incident_doc
    
    async def get_all_incidents(
        self,
        skip: int = 0,
        limit: int = 100,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        camera_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all incidents with filters"""
        
        query = {}
        if severity:
            query["severity"] = severity
        if status:
            query["status"] = status
        if camera_id:
            query["camera_id"] = camera_id
        
        cursor = self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        incidents = await cursor.to_list(length=limit)
        
        for inc in incidents:
            inc["_id"] = str(inc["_id"])
        
        return incidents
    
    async def get_incident_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Get single incident by ID"""
        
        # Try to find by incident_id field first
        incident = await self.collection.find_one({"incident_id": incident_id})
        
        # If not found, try ObjectId
        if not incident:
            try:
                incident = await self.collection.find_one({"_id": ObjectId(incident_id)})
            except:
                return None
        
        if incident:
            incident["_id"] = str(incident["_id"])
        
        return incident
    
    async def update_incident_status(
        self,
        incident_id: str,
        status: IncidentStatus
    ) -> Optional[Dict[str, Any]]:
        """Update incident status"""
        
        update_data = {
            "status": status.value,
            "updated_at": datetime.now()
        }
        
        result = await self.collection.find_one_and_update(
            {"incident_id": incident_id},
            {"$set": update_data},
            return_document=True
        )
        
        if result:
            result["_id"] = str(result["_id"])
        
        return result
    
    async def get_recent_incidents(self, hours: int = 24, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent incidents within last N hours"""
        
        since = datetime.now() - timedelta(hours=hours)
        
        cursor = self.collection.find(
            {"timestamp": {"$gte": since}}
        ).sort("timestamp", -1).limit(limit)
        
        incidents = await cursor.to_list(length=limit)
        
        for inc in incidents:
            inc["_id"] = str(inc["_id"])
        
        return incidents
    
    async def get_incidents_by_severity(self, severity: SeverityLevel) -> int:
        """Count incidents by severity"""
        return await self.collection.count_documents({"severity": severity.value})
    
    async def get_violations_today(self) -> int:
        """Get total violations today"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.collection.count_documents({"timestamp": {"$gte": today_start}})
    
    async def get_violation_trend(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get violation trend for last N hours"""
        
        since = datetime.now() - timedelta(hours=hours)
        
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%H:00",
                        "date": "$timestamp"
                    }
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        
        return [{"hour": r["_id"], "violations": r["count"]} for r in results]
    
    async def get_top_violations(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top violation types"""
        
        pipeline = [
            {"$group": {
                "_id": "$violation_type",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        
        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        
        return [{"type": r["_id"], "count": r["count"]} for r in results]
    
    async def _update_offender(self, license_plate: str, violation_type: str):
        """Update offender tracking"""
        
        offenders = self.db.offenders
        
        await offenders.update_one(
            {"license_plate": license_plate},
            {
                "$inc": {"total_violations": 1},
                "$push": {
                    "violations": {
                        "type": violation_type,
                        "timestamp": datetime.now()
                    }
                },
                "$set": {
                    "last_seen": datetime.now(),
                    "is_repeat_offender": True  # Mark as repeat if > 1 violation
                },
                "$setOnInsert": {
                    "first_seen": datetime.now()
                }
            },
            upsert=True
        )
    
    async def _update_camera(self, camera_id: str, location: str, coords: Dict[str, float]):
        """Update camera last seen"""
        
        cameras = self.db.cameras
        
        await cameras.update_one(
            {"camera_id": camera_id},
            {
                "$set": {
                    "last_seen": datetime.now(),
                    "status": "active"
                },
                "$setOnInsert": {
                    "name": location,
                    "location": {
                        "name": location,
                        "lat": coords["lat"],
                        "lng": coords["lng"]
                    }
                }
            },
            upsert=True
        )
