"""
Model Service - Integration with AI Detection Models

This service handles communication with the AI model service
(running on Colab, Hugging Face, or local server)
"""

import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from ..config import settings
from .yolo_service import get_yolo_service, YOLO_AVAILABLE


class ModelService:
    """Service for communicating with AI model (embedded in-process)"""
    
    def __init__(self, model_url: Optional[str] = None):
        """
        Initialize model service
        """
        self.model_url = "embedded"
        self.timeout = 30.0
    
    async def detect_violations(
        self, 
        image_path: str,
        camera_id: str,
        timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run violation detection in-process using YoloService (from file path)."""
        try:
            yolo = get_yolo_service()
            result = await asyncio.to_thread(yolo.detect_from_file, image_path, camera_id)
            if timestamp:
                result["timestamp"] = timestamp
            return result
        except Exception as e:
            raise Exception(f"Error executing embedded model: {str(e)}")

    async def detect_violations_from_bytes(
        self,
        image_bytes: bytes,
        camera_id: str,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run violation detection directly from raw image bytes — no local file needed."""
        try:
            yolo = get_yolo_service()
            result = await asyncio.to_thread(yolo.detect_from_bytes, image_bytes, camera_id)
            if timestamp:
                result["timestamp"] = timestamp
            return result
        except Exception as e:
            raise Exception(f"Error executing embedded model (bytes): {str(e)}")


    
    async def detect_violations_batch(
        self,
        image_paths: List[str],
        camera_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Process multiple images in batch
        
        Args:
            image_paths: List of image file paths
            camera_ids: List of corresponding camera IDs
            
        Returns:
            List of detection results
        """
        results = []
        for image_path, camera_id in zip(image_paths, camera_ids):
            try:
                result = await self.detect_violations(image_path, camera_id)
                results.append(result)
            except Exception as e:
                # Log error but continue with other images
                print(f"Error processing {image_path}: {str(e)}")
                results.append({
                    "error": str(e),
                    "image_path": image_path,
                    "camera_id": camera_id
                })
        
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check if model service is available
        
        Returns:
            Health status of model service
        """
        if YOLO_AVAILABLE:
            return {
                "status": "healthy",
                "model_url": "embedded",
                "response": {"status": "ok", "message": "Embedded YOLO models active"}
            }
        else:
            return {
                "status": "unhealthy",
                "model_url": "embedded",
                "error": "YOLO (ultralytics) dependency is not installed"
            }
    
    def process_model_output(self, model_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform model output to backend format
        
        Args:
            model_output: Raw output from model
            
        Returns:
            Transformed data ready for incident creation
        """
        # Extract violations from model output
        violations = model_output.get("violations", [])
        
        if not violations:
            return None
        
        # Take the primary (highest confidence) violation
        primary_violation = violations[0]
        
        # Transform to backend format
        incident_data = {
            "violation_type": primary_violation.get("type"),
            "confidence": primary_violation.get("confidence"),
            "severity": self._calculate_severity(primary_violation),
            "camera_id": model_output.get("camera_id"),
            "timestamp": model_output.get("timestamp"),
            "location": model_output.get("location", {}),
            "license_plates": model_output.get("license_plates", []),
            "evidence_image": model_output.get("evidence_image"),
            "detected_objects": model_output.get("detected_objects", []),
            "all_violations": violations,  # Store all detected violations
            "model_metadata": {
                "model_version": model_output.get("model_version"),
                "inference_time": model_output.get("inference_time"),
                "device": model_output.get("device", "unknown")
            }
        }
        
        return incident_data
    
    def _calculate_severity(self, violation: Dict[str, Any]) -> str:
        """
        Calculate severity based on violation type and confidence
        
        Args:
            violation: Violation data from model
            
        Returns:
            Severity level (low, medium, high, critical)
        """
        violation_type = violation.get("type", "").lower()
        confidence = violation.get("confidence", 0)
        
        # Critical violations (life-threatening)
        if violation_type in ["accident", "wrong_way", "red_light"]:
            return "critical" if confidence > 0.7 else "high"
        
        # High severity
        if violation_type in ["no_helmet", "no_seatbelt", "overspeeding"]:
            return "high" if confidence > 0.7 else "medium"
        
        # Medium severity
        if violation_type in ["triple_riding", "stopline", "illegal_parking"]:
            return "medium" if confidence > 0.6 else "low"
        
        # Default
        return "medium" if confidence > 0.6 else "low"


# Singleton instance
_model_service = None

def get_model_service() -> ModelService:
    """Get or create ModelService singleton"""
    global _model_service
    if _model_service is None:
        _model_service = ModelService()
    return _model_service
