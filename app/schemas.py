from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
import re


# ---------------------------------------------------------------------------
# Cloudinary Submission Schema
# ---------------------------------------------------------------------------

CLOUDINARY_URL_PATTERN = re.compile(
    r"^https://res\.cloudinary\.com/[\w-]+/video/upload/.+\.(?:mp4|mov|avi|webm)(\?.*)?$",
    re.IGNORECASE,
)


class CloudinaryJobRequest(BaseModel):
    """Request body for submitting a Cloudinary-hosted video URL for 3D reconstruction."""

    cloudinary_url: str = Field(
        ...,
        description=(
            "Public Cloudinary video delivery URL. "
            "Must start with https://res.cloudinary.com/<cloud_name>/video/upload/ "
            "and end with a supported extension (.mp4, .mov, .avi, .webm)."
        ),
        examples=["https://res.cloudinary.com/mycloud/video/upload/v123/disaster_clip.mp4"],
    )

    # --- Capture metadata (mirrors SplatCaptureBase) ---
    title: str = Field(..., max_length=255, description="Name of the location or damage zone")
    description: Optional[str] = Field(None, max_length=1000, description="Description of the disaster/damage")
    disaster_type: str = Field(..., description="Type of disaster (landslide, flood, wildfire, earthquake, other)")
    severity: str = Field(..., description="Severity classification (low, medium, high, critical)")

    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude coordinate")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude coordinate")
    altitude: float = Field(0.0, description="Elevation above sea level in meters")

    roll: float = Field(0.0, description="Orientation roll rotation (degrees)")
    pitch: float = Field(0.0, description="Orientation pitch rotation (degrees)")
    yaw: float = Field(0.0, description="Orientation yaw rotation (degrees)")

    scale_x: float = Field(1.0, description="Scale multiplier on X-axis")
    scale_y: float = Field(1.0, description="Scale multiplier on Y-axis")
    scale_z: float = Field(1.0, description="Scale multiplier on Z-axis")

    @field_validator("cloudinary_url")
    @classmethod
    def validate_cloudinary_url(cls, v: str) -> str:
        if not CLOUDINARY_URL_PATTERN.match(v):
            raise ValueError(
                "Invalid Cloudinary URL. Must match: "
                "https://res.cloudinary.com/<cloud>/video/upload/....<mp4|mov|avi|webm>"
            )
        return v


# ---------------------------------------------------------------------------


class SplatCaptureBase(BaseModel):
    title: str = Field(..., max_length=255, description="Name of the location or damage zone")
    description: Optional[str] = Field(None, max_length=1000, description="Description of the disaster/damage")
    disaster_type: str = Field(..., description="Type of disaster (landslide, flood, wildfire, earthquake, other)")
    severity: str = Field(..., description="Severity classification (low, medium, high, critical)")
    
    # Geolocation
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude coordinate")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude coordinate")
    altitude: float = Field(0.0, description="Elevation above sea level in meters")
    
    # Orientation (Roll, Pitch, Yaw)
    roll: float = Field(0.0, description="Orientation roll rotation (degrees)")
    pitch: float = Field(0.0, description="Orientation pitch rotation (degrees)")
    yaw: float = Field(0.0, description="Orientation yaw rotation (degrees)")
    
    # Scale multipliers
    scale_x: float = Field(1.0, description="Scale dimension multiplier on X-axis")
    scale_y: float = Field(1.0, description="Scale dimension multiplier on Y-axis")
    scale_z: float = Field(1.0, description="Scale dimension multiplier on Z-axis")


class SplatCaptureCreate(SplatCaptureBase):
    pass


class SplatCaptureUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    disaster_type: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    roll: Optional[float] = None
    pitch: Optional[float] = None
    yaw: Optional[float] = None
    scale_x: Optional[float] = None
    scale_y: Optional[float] = None
    scale_z: Optional[float] = None


class SplatCaptureResponse(SplatCaptureBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# GeoJSON Compliant Schemas for Flutter Map Integrations (Stage 3)
class GeoJSONGeometry(BaseModel):
    type: str = "Point"
    coordinates: list[float] = Field(..., description="[longitude, latitude, altitude]")


class GeoJSONFeatureProperties(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    disaster_type: str
    severity: str
    status: str
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    roll: float
    pitch: float
    yaw: float
    scale_x: float
    scale_y: float
    scale_z: float
    created_at: datetime


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: GeoJSONFeatureProperties


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoJSONFeature]


# Job Processing Schemas
class ProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    capture_id: str
    video_url: Optional[str] = None
    task_id: Optional[str] = None
    progress: int
    status_message: str
    error_log: Optional[str] = None
    created_at: datetime
    updated_at: datetime
