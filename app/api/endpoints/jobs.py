from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SplatCapture, ProcessingJob
from app.schemas import ProcessingJobResponse, CloudinaryJobRequest
from app.services.storage import storage_service
from app.tasks import execute_reconstruction_pipeline, execute_reconstruction_pipeline_from_url

router = APIRouter()


@router.post("/upload-video", response_model=ProcessingJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_disaster_video(
    background_tasks: BackgroundTasks,
    title: str = Form(..., description="Name of the disaster zone / capture location"),
    description: str = Form(None, description="Detailed damage description"),
    disaster_type: str = Form(..., description="Type of disaster"),
    severity: str = Form(..., description="Damage severity level"),
    latitude: float = Form(..., description="Camera start/anchor latitude coordinate"),
    longitude: float = Form(..., description="Camera start/anchor longitude coordinate"),
    altitude: float = Form(0.0, description="Altitude/Elevation"),
    file: UploadFile = File(..., description="Raw MP4 or MOV video file capture"),
    db: Session = Depends(get_db)
):
    """
    Stage 2 Video Ingestion - User uploads a video and geolocational tags.
    Creates a pending SplatCapture, registers a ProcessingJob, and schedules
    the async reconstruction task.
    """
    # 1. Validate video format
    filename = file.filename or ""
    if not (filename.endswith(".mp4") or filename.endswith(".mov") or filename.endswith(".avi")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid video format. Supported formats: .mp4, .mov, .avi"
        )
        
    # 2. Create SplatCapture Shell
    capture = SplatCapture(
        title=title,
        description=description,
        disaster_type=disaster_type,
        severity=severity,
        status="pending",
        latitude=latitude,
        longitude=longitude,
        altitude=altitude
    )
    db.add(capture)
    db.commit()
    db.refresh(capture)
    
    # 3. Save uploaded video file
    video_url = await storage_service.save_uploaded_file(file, folder="videos")
    
    # 4. Create ProcessingJob entry
    job = ProcessingJob(
        capture_id=capture.id,
        video_url=video_url,
        progress=0,
        status_message="Video uploaded successfully. Starting pipeline..."
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # 5. Delegate to asynchronous worker
    # By default, use FastAPI's asynchronous thread-pool.
    # Can be swapped to celery: celery_app.send_task("tasks.execute_reconstruction_pipeline", args=[job.id])
    background_tasks.add_task(execute_reconstruction_pipeline, job.id)
    
    return job


@router.get("/{job_id}", response_model=ProcessingJobResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Retrieves the active state and training progression of a reconstruction job.
    The Flutter client can poll this endpoint to show progress indicator (0 - 100%).
    """
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Processing job not found")
    return job


@router.get("/capture/{capture_id}", response_model=ProcessingJobResponse)
def get_job_by_capture(capture_id: str, db: Session = Depends(get_db)):
    """
    Retrieves the job associated with a specific Splat Capture.
    """
    job = db.query(ProcessingJob).filter(ProcessingJob.capture_id == capture_id).order_by(ProcessingJob.created_at.desc()).first()
    if not job:
        raise HTTPException(status_code=404, detail="No processing job found for this capture")
    return job


@router.post(
    "/submit-cloudinary",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Cloudinary video URL for 3D reconstruction",
)
async def submit_cloudinary_video(
    payload: CloudinaryJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Stage 2 (Cloudinary variant) — Accept a **Cloudinary delivery URL** instead
    of a raw file upload.  The URL is validated, stored, and forwarded directly
    to the Luma AI reconstruction API (or the internal simulation pipeline when
    no ``LUMA_API_KEY`` is set).

    **Request body** (JSON):
    ```json
    {
      "cloudinary_url": "https://res.cloudinary.com/mycloud/video/upload/v123/clip.mp4",
      "title": "Flood Zone A",
      "disaster_type": "flood",
      "severity": "high",
      "latitude": 27.7172,
      "longitude": 85.3240
    }
    ```

    **Returns** a `ProcessingJobResponse` immediately (HTTP 202).  Poll
    `GET /api/v1/jobs/{job_id}` to track progress.
    """
    # 1. Create SplatCapture shell
    capture = SplatCapture(
        title=payload.title,
        description=payload.description,
        disaster_type=payload.disaster_type,
        severity=payload.severity,
        status="pending",
        latitude=payload.latitude,
        longitude=payload.longitude,
        altitude=payload.altitude,
        roll=payload.roll,
        pitch=payload.pitch,
        yaw=payload.yaw,
        scale_x=payload.scale_x,
        scale_y=payload.scale_y,
        scale_z=payload.scale_z,
    )
    db.add(capture)
    db.commit()
    db.refresh(capture)

    # 2. Create ProcessingJob — store the Cloudinary URL in video_url
    job = ProcessingJob(
        capture_id=capture.id,
        video_url=payload.cloudinary_url,  # Cloudinary URL, no local file
        progress=0,
        status_message="Cloudinary URL received. Starting reconstruction pipeline...",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 3. Kick off the Cloudinary-aware background pipeline
    background_tasks.add_task(execute_reconstruction_pipeline_from_url, job.id)

    return job
