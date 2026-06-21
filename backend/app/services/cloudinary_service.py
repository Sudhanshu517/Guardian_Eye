"""
CloudinaryService — Reusable upload utility for evidence images.

Credentials are read exclusively from environment variables via the app Settings.
If any required credential (cloud_name, api_key, api_secret) is missing or contains
the default placeholder text, the service disables itself and every upload call
returns None — no exception is raised, allowing the system to continue with
local file fallback behaviour.
"""

import os
from typing import Optional, Dict, Any
from ..config import settings

# ── SDK import (optional dependency) ─────────────────────────────────────────
try:
    import cloudinary
    import cloudinary.uploader
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False
    print("⚠️  cloudinary SDK not installed — evidence images will NOT be uploaded to cloud")


# Placeholder sentinel strings that appear in the template .env file
_PLACEHOLDERS = {"your_cloud_name_here", "your_api_key_here", "your_api_secret_here", "", None}


def _credentials_configured() -> bool:
    """Return True only when all three real Cloudinary credentials are present."""
    return (
        CLOUDINARY_AVAILABLE
        and settings.cloudinary_cloud_name not in _PLACEHOLDERS
        and settings.cloudinary_api_key not in _PLACEHOLDERS
        and settings.cloudinary_api_secret not in _PLACEHOLDERS
    )


class CloudinaryService:
    """
    Thin wrapper around the Cloudinary Python SDK.

    Usage:
        svc = get_cloudinary_service()
        result = svc.upload_evidence("/path/to/frame.jpg", public_id_prefix="CAM-001")
        if result:
            cloudinary_url = result["secure_url"]
    """

    def __init__(self):
        self._enabled = _credentials_configured()
        if self._enabled:
            cloudinary.config(
                cloud_name=settings.cloudinary_cloud_name,
                api_key=settings.cloudinary_api_key,
                api_secret=settings.cloudinary_api_secret,
                secure=True,
            )
            print(
                f"[Cloudinary] Configured: cloud={settings.cloudinary_cloud_name}, "
                f"folder={settings.cloudinary_folder}"
            )
        else:
            if CLOUDINARY_AVAILABLE:
                print(
                    "[Cloudinary] WARNING: Credentials not set — "
                    "evidence images will be served from local storage. "
                    "Set CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET in .env to enable cloud uploads."
                )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def upload_evidence(
        self,
        local_path: str,
        public_id_prefix: str = "evidence",
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a local evidence image file to Cloudinary.

        Args:
            local_path:        Absolute or relative path to the image file on disk.
            public_id_prefix:  Prefix used to build the Cloudinary public_id.
                               Example: "CAM-001" → public_id "guardianeye/evidence/CAM-001_<filename>"

        Returns:
            Dict with keys: url, secure_url, public_id, resource_type, format
            or None if the service is disabled or the upload failed.
        """
        if not self._enabled:
            return None

        if not os.path.isfile(local_path):
            print(f"[Cloudinary] Upload skipped — file not found: {local_path}")
            return None

        filename_stem = os.path.splitext(os.path.basename(local_path))[0]
        public_id = f"{settings.cloudinary_folder}/{public_id_prefix}_{filename_stem}"

        try:
            response = cloudinary.uploader.upload(
                local_path,
                public_id=public_id,
                overwrite=False,
                resource_type="image",
                tags=["guardianeye", "evidence", "traffic-violation"],
            )
            print(
                f"[Cloudinary] Uploaded: {response.get('secure_url')} "
                f"(public_id={response.get('public_id')})"
            )
            return {
                "url": response.get("url"),
                "secure_url": response.get("secure_url"),
                "public_id": response.get("public_id"),
                "resource_type": response.get("resource_type"),
                "format": response.get("format"),
                "bytes": response.get("bytes"),
            }
        except Exception as exc:
            # Log the failure but never raise — the caller should handle None gracefully
            print(f"[Cloudinary] Upload FAILED for {local_path}: {exc}")
            return None

    def upload_evidence_bytes(
        self,
        image_bytes: bytes,
        public_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Upload raw image bytes to Cloudinary (useful when no local file is written).

        Args:
            image_bytes: Raw image data.
            public_id:   Full Cloudinary public_id (including folder path).

        Returns:
            Same dict as upload_evidence(), or None on failure/disabled.
        """
        if not self._enabled:
            return None

        try:
            import io
            response = cloudinary.uploader.upload(
                io.BytesIO(image_bytes),
                public_id=public_id,
                overwrite=False,
                resource_type="image",
                tags=["guardianeye", "evidence", "traffic-violation"],
            )
            print(f"[Cloudinary] Uploaded bytes: {response.get('secure_url')}")
            return {
                "url": response.get("url"),
                "secure_url": response.get("secure_url"),
                "public_id": response.get("public_id"),
                "resource_type": response.get("resource_type"),
                "format": response.get("format"),
                "bytes": response.get("bytes"),
            }
        except Exception as exc:
            print(f"[Cloudinary] Upload (bytes) FAILED: {exc}")
            return None


# ── Singleton ──────────────────────────────────────────────────────────────────
_cloudinary_service: Optional[CloudinaryService] = None


def get_cloudinary_service() -> CloudinaryService:
    """Return (or lazily create) the process-level CloudinaryService singleton."""
    global _cloudinary_service
    if _cloudinary_service is None:
        _cloudinary_service = CloudinaryService()
    return _cloudinary_service
