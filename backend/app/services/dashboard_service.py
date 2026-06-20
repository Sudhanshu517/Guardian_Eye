from datetime import datetime, timedelta
from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..models.schemas import DashboardStats, HeatmapPoint, SeverityLevel
from ..utils.helpers import calculate_avg_response_time


class DashboardService:
    """Service for dashboard data"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics"""
        
        incidents = self.db.incidents
        alerts = self.db.alerts
        cameras = self.db.cameras
        
        # Time boundaries
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        last_24h = datetime.now() - timedelta(hours=24)
        
        # Violations today
        violations_today = await incidents.count_documents({
            "timestamp": {"$gte": today_start}
        })
        
        # Active accidents (assuming accident violations in last hour)
        last_hour = datetime.now() - timedelta(hours=1)
        active_accidents = await incidents.count_documents({
            "violation_type": "accident",
            "timestamp": {"$gte": last_hour},
            "status": {"$in": ["new", "alert_sent", "acknowledged"]}
        })
        
        # High severity alerts
        high_severity_alerts = await alerts.count_documents({
            "severity": {"$in": ["high", "critical"]},
            "status": {"$in": ["sent", "acknowledged"]}
        })
        
        # Pending responses
        pending_police = await alerts.count_documents({
            "type": "police",
            "status": {"$in": ["sent", "pending"]}
        })
        
        pending_hospital = await alerts.count_documents({
            "type": "hospital",
            "status": {"$in": ["sent", "pending"]}
        })
        
        # Camera stats
        total_cameras = await cameras.count_documents({})
        active_cameras = await cameras.count_documents({
            "status": "active",
            "last_seen": {"$gte": datetime.now() - timedelta(minutes=5)}
        })
        
        # Average response time
        all_alerts = await alerts.find({}).to_list(length=1000)
        avg_response = calculate_avg_response_time(all_alerts)
        
        # City safety score (mock calculation)
        city_safety_score = await self._calculate_safety_score(incidents)
        
        # Violation trend
        violation_trend = await self._get_violation_trend(incidents, hours=24)
        
        # Top violations
        top_violations = await self._get_top_violations(incidents)
        
        # Severity distribution
        severity_dist = await self._get_severity_distribution(incidents)
        
        return {
            # Keys for dashboard frontend (index.tsx)
            "total_incidents_today": violations_today,
            "violations_today": violations_today,        # keep alias
            "active_accidents": active_accidents,
            "high_severity_alerts": high_severity_alerts,
            "pending_police_alerts": pending_police,
            "pending_police_response": pending_police,   # keep alias
            "pending_hospital_alerts": pending_hospital,
            "pending_hospital_response": pending_hospital,  # keep alias
            "active_cameras": active_cameras,
            "total_cameras": total_cameras,
            "avg_response_time": avg_response,
            "safety_score": city_safety_score,
            "city_safety_score": city_safety_score,     # keep alias
            "violation_trend": violation_trend,
            "top_violations": top_violations,
            "severity_distribution": severity_dist,
        }
    
    async def get_heatmap_data(self) -> List[Dict[str, Any]]:
        """Get violation heatmap data"""
        
        incidents = self.db.incidents
        
        # Get incidents from last 7 days with location data
        since = datetime.now() - timedelta(days=7)
        
        pipeline = [
            {"$match": {
                "timestamp": {"$gte": since},
                "location.lat": {"$exists": True},
                "location.lng": {"$exists": True}
            }},
            {"$group": {
                "_id": {
                    "lat": "$location.lat",
                    "lng": "$location.lng",
                    "name": "$location.name"
                },
                "count": {"$sum": 1},
                "severity": {"$first": "$severity"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 100}
        ]
        
        cursor = incidents.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        
        heatmap_points = []
        for r in results:
            heatmap_points.append({
                "lat": r["_id"]["lat"],
                "lng": r["_id"]["lng"],
                "location_name": r["_id"]["name"],
                "count": r["count"],
                "severity": r["severity"]
            })
        
        return heatmap_points
    
    async def _calculate_safety_score(self, incidents_collection) -> int:
        """Calculate city safety score (0-100, higher is safer)"""
        
        # Get violations from last 7 days
        since = datetime.now() - timedelta(days=7)
        
        total = await incidents_collection.count_documents({
            "timestamp": {"$gte": since}
        })
        
        critical = await incidents_collection.count_documents({
            "timestamp": {"$gte": since},
            "severity": "critical"
        })
        
        high = await incidents_collection.count_documents({
            "timestamp": {"$gte": since},
            "severity": "high"
        })
        
        # Simple scoring algorithm
        if total == 0:
            return 100
        
        # Weighted score
        penalty = (critical * 10 + high * 5 + (total - critical - high) * 1)
        score = max(0, 100 - (penalty // 10))
        
        return min(100, score)
    
    async def _get_violation_trend(self, incidents_collection, hours: int = 24) -> List[Dict[str, Any]]:
        """Get hourly violation trend"""
        
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
                "violations": {"$sum": 1},
                "accidents": {
                    "$sum": {
                        "$cond": [{"$eq": ["$violation_type", "accident"]}, 1, 0]
                    }
                }
            }},
            {"$sort": {"_id": 1}}
        ]
        
        cursor = incidents_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        
        return [
            {
                "hour": r["_id"],
                "violations": r["violations"],
                "accidents": r["accidents"]
            }
            for r in results
        ]
    
    async def _get_top_violations(self, incidents_collection, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top violation types"""
        
        pipeline = [
            {"$group": {
                "_id": "$violation_type",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        
        cursor = incidents_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        
        return [{"type": r["_id"], "count": r["count"]} for r in results]
    
    async def _get_severity_distribution(self, incidents_collection) -> Dict[str, int]:
        """Get distribution of incidents by severity"""
        
        pipeline = [
            {"$group": {
                "_id": "$severity",
                "count": {"$sum": 1}
            }}
        ]
        
        cursor = incidents_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        
        distribution = {
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0
        }
        
        for r in results:
            distribution[r["_id"]] = r["count"]
        
        return distribution
