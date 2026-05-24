from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SplatCapture, ProcessingJob
from app.schemas import ProcessingJobResponse
from app.services.storage import storage_service
from app.tasks import execute_reconstruction_pipeline

router = APIRouter()


@router.get("/", response_model=list[ProcessingJobResponse])
def get_all_jobs(db: Session = Depends(get_db)):
    """
    List all processing jobs ordered by creation time (most recent first).
    """
    return db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).all()


@router.get("/capture/{capture_id}", response_model=ProcessingJobResponse)
def get_job_by_capture(capture_id: str, db: Session = Depends(get_db)):
    """
    Retrieves the most-recent job associated with a specific SplatCapture ID.
    Used by the frontend to poll reconstruction progress.
    """
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.capture_id == capture_id)
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No processing job found for this capture")
    return job


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
    file: UploadFile = File(..., description="Raw MP4, MOV, or AVI video file capture"),
    db: Session = Depends(get_db),
):
    """
    Video Ingestion — accepts a raw video file as multipart/form-data along with
    geospatial metadata. Saves the video to the local uploads directory, creates a
    SplatCapture and ProcessingJob in the DB, then queues the reconstruction pipeline
    as a background task.

    The video is stored under static/videos/ and the path is written to the job's
    video_url field so the pipeline can locate it on disk.
    """
    # Normalise the filename: React Native temp URIs sometimes lack an extension
    filename = file.filename or "capture.mp4"
    fname_lower = filename.lower()
    if "." not in filename:
        filename = filename + ".mp4"
        fname_lower = filename.lower()

    if not (fname_lower.endswith(".mp4") or fname_lower.endswith(".mov") or fname_lower.endswith(".avi")):
        raise HTTPException(
            status_code=400,
            detail="Invalid video format. Supported formats: .mp4, .mov, .avi"
        )

    # 1. Create SplatCapture shell (status=pending)
    capture = SplatCapture(
        title=title,
        description=description,
        disaster_type=disaster_type,
        severity=severity,
        status="pending",
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
    )
    db.add(capture)
    db.commit()
    db.refresh(capture)

    # 2. Stream the uploaded file to disk: static/videos/<uuid>.<ext>
    file.filename = filename  # ensure storage service uses the corrected name
    video_url = await storage_service.save_uploaded_file(file, folder="videos")

    # 3. Create ProcessingJob linked to the capture
    job = ProcessingJob(
        capture_id=capture.id,
        video_url=video_url,
        progress=0,
        status_message="Video received. Queuing reconstruction pipeline...",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 4. Kick off the background reconstruction task
    background_tasks.add_task(execute_reconstruction_pipeline, job.id)

    return job


# NOTE: /{job_id} is a catch-all — MUST be declared LAST so it does not shadow
# more specific routes like /capture/{capture_id} or /.
@router.get("/{job_id}", response_model=ProcessingJobResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Retrieve the current state and progress (0-100%) of a reconstruction job.
    Poll this endpoint to drive progress indicators on the frontend.
    """
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Processing job not found")
    return job
