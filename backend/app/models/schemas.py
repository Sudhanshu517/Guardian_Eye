from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    NEW = "new"
    ALERT_SENT = "alert_sent"
    IN_REVIEW = "in_review"
    ACKNOWLEDGED = "acknowledged"
    DISPATCHED = "dispatched"
    RESOLVED = "resolved"


class AlertType(str, Enum):
    POLICE = "police"
    HOSPITAL = "hospital"
    AMBULANCE = "ambulance"


class AlertStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"


class LocationSchema(BaseModel):
    name: str
    lat: Optional[float] = None
    lng: Optional[float] = None


class ViolationSchema(BaseModel):
    type: str
    class_name: str = Field(alias="class")
    confidence: float
    score: int
    severity: str
    time: str
    
    class Config:
        populate_by_name = True


class DetectionInput(BaseModel):
    """Input from AI model"""
    timestamp: str
    camera_id: str
    location: str
    peak_hour: Optional[str] = None
    weather: Optional[str] = None
    total_score: int
    overall_severity: str
    violations: List[ViolationSchema]
    license_plates: List[str]
    alert_sent: bool = False
    image: Optional[str] = None
    cloudinary_url: Optional[str] = None
    cloudinary_public_id: Optional[str] = None
    statistics: Optional[Dict[str, Any]] = None


class IncidentCreate(BaseModel):
    """Schema for creating an incident"""
    camera_id: str
    timestamp: datetime
    location: LocationSchema
    violation_type: str
    severity: SeverityLevel
    total_score: int
    confidence: float
    license_plates: List[str] = []
    violations: List[Dict[str, Any]] = []
    evidence_image: Optional[str] = None
    cloudinary_url: Optional[str] = None
    cloudinary_public_id: Optional[str] = None
    peak_hour: Optional[str] = None
    weather: Optional[str] = None


class IncidentResponse(BaseModel):
    """Schema for incident response"""
    id: str = Field(alias="_id")
    incident_id: str
    camera_id: str
    timestamp: datetime
    location: LocationSchema
    violation_type: str
    severity: SeverityLevel
    total_score: int
    confidence: float
    license_plates: List[str]
    violations: List[Dict[str, Any]]
    evidence_image: Optional[str]
    cloudinary_url: Optional[str] = None
    cloudinary_public_id: Optional[str] = None
    status: IncidentStatus
    alert_sent: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


class IncidentUpdateStatus(BaseModel):
    """Schema for updating incident status"""
    status: IncidentStatus


class AlertCreate(BaseModel):
    """Schema for creating an alert"""
    incident_id: str
    type: AlertType
    severity: SeverityLevel
    recipient: str
    message: str


class AlertResponse(BaseModel):
    """Schema for alert response"""
    id: str = Field(alias="_id")
    alert_id: str
    incident_id: str
    type: AlertType
    severity: SeverityLevel
    recipient: str
    message: str
    status: AlertStatus
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        populate_by_name = True


class CameraSchema(BaseModel):
    """Schema for camera"""
    camera_id: str
    name: str
    location: LocationSchema
    status: str = "active"
    last_seen: datetime


class CameraResponse(BaseModel):
    """Schema for camera response"""
    id: str = Field(alias="_id")
    camera_id: str
    name: str
    location: LocationSchema
    status: str
    last_seen: datetime
    total_detections: int = 0
    
    class Config:
        populate_by_name = True


class OffenderSchema(BaseModel):
    """Schema for repeat offender"""
    license_plate: str
    total_violations: int = 0
    violations: List[Dict[str, Any]] = []
    is_repeat_offender: bool = False
    first_seen: datetime
    last_seen: datetime


class DashboardStats(BaseModel):
    """Dashboard statistics"""
    violations_today: int
    active_accidents: int
    high_severity_alerts: int
    pending_police_response: int
    pending_hospital_response: int
    active_cameras: int
    total_cameras: int
    avg_response_time: str
    city_safety_score: int
    violation_trend: List[Dict[str, Any]]
    top_violations: List[Dict[str, Any]]
    severity_distribution: Dict[str, int]


class HeatmapPoint(BaseModel):
    """Heatmap data point"""
    lat: float
    lng: float
    severity: SeverityLevel
    count: int
    location_name: str
