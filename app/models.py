import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class SplatCapture(Base):
    __tablename__ = "splat_captures"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    disaster_type = Column(String(50), nullable=False)  # wildfire, flood, landslide, earthquake, other
    severity = Column(String(20), nullable=False)       # low, medium, high, critical
    status = Column(String(20), default="pending")      # pending, processing, completed, failed
    
    # File storage paths (locally hosted static URLs or S3 links)
    file_url = Column(String(512), nullable=True)
    thumbnail_url = Column(String(512), nullable=True)
    
    # Geolocation (WGS84 Coordinate Space)
    # Using float fields for database compatibility (Postgres/PostGIS maps ST_X/ST_Y here natively)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, default=0.0)  # Elevation in meters
    
    # Anchor calibration parameters for aligned rendering in Flutter Map/3D Canvas
    # Rotation (Roll, Pitch, Yaw in degrees or radians as required by Flutter client)
    roll = Column(Float, default=0.0)
    pitch = Column(Float, default=0.0)
    yaw = Column(Float, default=0.0)
    
    # Scale values to stretch/shrink the physical model in 3D canvas (meters per unit)
    scale_x = Column(Float, default=1.0)
    scale_y = Column(Float, default=1.0)
    scale_z = Column(Float, default=1.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("ProcessingJob", back_populates="capture", cascade="all, delete-orphan")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    capture_id = Column(String(36), ForeignKey("splat_captures.id"), nullable=False)
    video_url = Column(String(512), nullable=True)
    task_id = Column(String(255), nullable=True)  # Background task tracking id
    progress = Column(Integer, default=0)         # 0 - 100 percent
    status_message = Column(String(255), default="Initialized")
    error_log = Column(String(2000), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    capture = relationship("SplatCapture", back_populates="jobs")
