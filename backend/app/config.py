from pydantic_settings import BaseSettings
from typing import Optional

import os

class Settings(BaseSettings):
    """Application settings and configuration"""
    
    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "guardianeye"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # CORS
    frontend_url: str = "http://localhost:3000"
    
    # Twilio (for SMS/WhatsApp alerts)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None
    
    # File Upload
    max_file_size: int = 10485760  # 10MB
    evidence_dir: str = "./evidence"
    models_dir: str = "./models"
    base_dir: str = "."
    
    # AI Model Service
    model_api_url: str = "http://localhost:8001"  # URL where model API is running
    model_timeout: int = 30  # Timeout in seconds for model inference

    # Cloudinary (evidence image cloud storage)
    # Set all three to enable automatic Cloudinary uploads of evidence frames.
    # If any is missing, uploads are silently skipped and local files are used as fallback.
    cloudinary_cloud_name: Optional[str] = None
    cloudinary_api_key: Optional[str] = None
    cloudinary_api_secret: Optional[str] = None
    cloudinary_folder: str = "guardianeye/evidence"
    
    def model_post_init(self, __context: object) -> None:
        """Log Cloudinary config status after .env is fully loaded."""
        cloud = self.cloudinary_cloud_name or "<not set>"
        key_status = "set" if self.cloudinary_api_key else "<not set>"
        print(f"[Config] Cloudinary cloud={cloud}, api_key={key_status}")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
