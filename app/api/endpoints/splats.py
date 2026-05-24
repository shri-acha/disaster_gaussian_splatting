from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SplatCapture
from app.schemas import (
    SplatCaptureCreate, 
    SplatCaptureResponse, 
    SplatCaptureUpdate,
    GeoJSONFeatureCollection,
    GeoJSONFeature,
    GeoJSONGeometry,
    GeoJSONFeatureProperties
)
from app.services.storage import storage_service
from app.services.geometry import geometry_service

router = APIRouter()


@router.post("/", response_model=SplatCaptureResponse, status_code=status.HTTP_201_CREATED)
def create_splat_metadata(payload: SplatCaptureCreate, db: Session = Depends(get_db)):
    """
    Creates a new georeferenced Splat Capture metadata shell.
    Use this to register an asset before uploading the .splat file or video.
    """
    db_splat = SplatCapture(**payload.model_dump())
    db.add(db_splat)
    db.commit()
    db.refresh(db_splat)
    return db_splat


@router.post("/{splat_id}/upload-asset", response_model=SplatCaptureResponse)
async def upload_direct_splat_file(
    splat_id: str, 
    file: UploadFile = File(..., description="The .splat or .ply binary asset"), 
    db: Session = Depends(get_db)
):
    """
    Stage 1 MVP - Directly upload a pre-processed 3D Gaussian Splat (.splat / .ply) 
    associated with a registered geospatial metadata shell.
    """
    db_splat = db.query(SplatCapture).filter(SplatCapture.id == splat_id).first()
    if not db_splat:
        raise HTTPException(status_code=404, detail="Splat metadata record not found")
        
    # Check file extension
    filename = file.filename or ""
    if not (filename.endswith(".ply") or filename.endswith(".splat")):
        raise HTTPException(status_code=400, detail="Invalid file format. Only .ply and .splat files are allowed")

    # Save to storage
    file_url = await storage_service.save_uploaded_file(file, folder="splats")
    
    # Update capture record
    db_splat.file_url = file_url
    db_splat.status = "completed"
    db.commit()
    db.refresh(db_splat)
    
    return db_splat


@router.get("/search", response_model=list[SplatCaptureResponse])
def search_splats_by_radius(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Center WGS84 latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Center WGS84 longitude"),
    radius_km: float = Query(5.0, gt=0.0, description="Search radius in kilometers"),
    db: Session = Depends(get_db)
):
    """
    Performs an immediate spatial search of all completed splats within a specific 
    distance from a center GPS coordinate. Fallback to haversine computation for local SQLite runtime.
    """
    # 1. Fetch completed splats from DB
    all_splats = db.query(SplatCapture).filter(SplatCapture.status == "completed").all()
    
    # 2. Filter using geometry calculation
    matching_splats = []
    for splat in all_splats:
        dist = geometry_service.haversine_distance(lat, lon, splat.latitude, splat.longitude)
        if dist <= radius_km:
            matching_splats.append(splat)
            
    return matching_splats


@router.get("/search/geojson", response_model=GeoJSONFeatureCollection)
def search_splats_geojson(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Center WGS84 latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Center WGS84 longitude"),
    radius_km: float = Query(5.0, gt=0.0, description="Search radius in kilometers"),
    db: Session = Depends(get_db)
):
    """
    Stage 3 Integration - Serves geospatial radius search results matching a GeoJSON 
    FeatureCollection structure. Perfect for standard Flutter Map components.
    """
    all_splats = db.query(SplatCapture).filter(SplatCapture.status == "completed").all()
    
    features = []
    for splat in all_splats:
        dist = geometry_service.haversine_distance(lat, lon, splat.latitude, splat.longitude)
        if dist <= radius_km:
            # Build standard GeoJSON Feature
            geometry = GeoJSONGeometry(
                type="Point",
                coordinates=[splat.longitude, splat.latitude, splat.altitude or 0.0]
            )
            properties = GeoJSONFeatureProperties(
                id=splat.id,
                title=splat.title,
                description=splat.description,
                disaster_type=splat.disaster_type,
                severity=splat.severity,
                status=splat.status,
                file_url=splat.file_url,
                thumbnail_url=splat.thumbnail_url,
                roll=splat.roll,
                pitch=splat.pitch,
                yaw=splat.yaw,
                scale_x=splat.scale_x,
                scale_y=splat.scale_y,
                scale_z=splat.scale_z,
                created_at=splat.created_at
            )
            feature = GeoJSONFeature(
                type="Feature",
                geometry=geometry,
                properties=properties
            )
            features.append(feature)
            
    return GeoJSONFeatureCollection(features=features)


@router.get("/{splat_id}", response_model=SplatCaptureResponse)
def get_splat_details(splat_id: str, db: Session = Depends(get_db)):
    """
    Retrieves full details of a specific Splat Capture.
    """
    splat = db.query(SplatCapture).filter(SplatCapture.id == splat_id).first()
    if not splat:
        raise HTTPException(status_code=404, detail="Splat capture not found")
    return splat


@router.patch("/{splat_id}", response_model=SplatCaptureResponse)
def update_splat_metadata(splat_id: str, payload: SplatCaptureUpdate, db: Session = Depends(get_db)):
    """
    Updates calibration tags or metadata metrics for a registered splat.
    """
    db_splat = db.query(SplatCapture).filter(SplatCapture.id == splat_id).first()
    if not db_splat:
        raise HTTPException(status_code=404, detail="Splat capture not found")
        
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_splat, key, value)
        
    db.commit()
    db.refresh(db_splat)
    return db_splat


@router.delete("/{splat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_splat_capture(splat_id: str, db: Session = Depends(get_db)):
    """
    Deletes the metadata record and removes the splat file and thumbnails from disk.
    """
    db_splat = db.query(SplatCapture).filter(SplatCapture.id == splat_id).first()
    if not db_splat:
        raise HTTPException(status_code=404, detail="Splat capture not found")
        
    # Delete local files if they exist
    if db_splat.file_url:
        storage_service.delete_file(db_splat.file_url)
    if db_splat.thumbnail_url:
        storage_service.delete_file(db_splat.thumbnail_url)
        
    db.delete(db_splat)
    db.commit()
    return None
