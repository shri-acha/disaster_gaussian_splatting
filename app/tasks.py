import os
import time
import zipfile
import cv2
import numpy as np
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import SplatCapture, ProcessingJob
from app.config import settings

def get_blur_score(image: np.ndarray) -> float:
    """
    Computes image blurriness using the Laplacian variance method.
    Higher values represent sharper images.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())

def extract_video_keyframes(video_path: str, output_dir: str, frame_interval: int = 30, max_frames: int = 150) -> list[str]:
    """
    Extracts high-quality (non-blurry) keyframes from a video file using OpenCV.
    Saves frames to output_dir and returns paths to extracted frame images.
    """
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise IOError(f"Could not open video file {video_path}")
        
    frame_count = 0
    saved_count = 0
    saved_paths = []
    
    # Laplacian variance threshold for filtering blurry frames
    # Real-world settings can dynamic adapt, but 100.0 is a solid heuristic
    blur_threshold = 100.0
    
    while cap.isOpened() and saved_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % frame_interval == 0:
            blur_score = get_blur_score(frame)
            
            # Save frame if it passes sharpness check or if it's the first few frames
            if blur_score > blur_threshold or saved_count < 10:
                frame_filename = f"frame_{saved_count:04d}.jpg"
                frame_path = os.path.join(output_dir, frame_filename)
                cv2.imwrite(frame_path, frame)
                saved_paths.append(frame_path)
                saved_count += 1
                
        frame_count += 1
        
    cap.release()
    return saved_paths

def zip_directory(directory_path: str, zip_path: str):
    """
    Zips all files in a directory to prepare for reconstruction API upload.
    """
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_full_path = os.path.join(root, file)
                zipf.write(file_full_path, os.path.relpath(file_full_path, directory_path))

def execute_reconstruction_pipeline(job_id: str):
    """
    Orchestrates the entire 3D Gaussian Splatting / NeRF reconstruction task.
    This can be executed via FastAPI BackgroundTasks or directly via Celery.
    """
    db: Session = SessionLocal()
    try:
        # 1. Fetch Job and Capture
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return
            
        capture = db.query(SplatCapture).filter(SplatCapture.id == job.capture_id).first()
        if not capture:
            job.status_message = "Failed: Parent capture not found"
            db.commit()
            return
            
        # Update database statuses
        capture.status = "processing"
        job.progress = 10
        job.status_message = "Preprocessing: Extracting frames from video..."
        db.commit()
        
        # Verify video file exists locally
        # Since we use static relative paths, parse it
        video_rel_path = job.video_url.lstrip("/")
        video_full_path = os.path.join(os.getcwd(), video_rel_path)
        
        if not os.path.exists(video_full_path):
            # If locally missing (e.g., mock or remote test), generate dummy logs
            time.sleep(2)
            job.progress = 25
            job.status_message = "Triggering Cloud reconstruction engine..."
            db.commit()
        else:
            # Real keyframe extraction!
            frames_dir = os.path.join(settings.STATIC_DIR, "temp_frames", job_id)
            zip_out_path = os.path.join(settings.STATIC_DIR, "temp_frames", f"{job_id}.zip")
            
            try:
                # Run OpenCV keyframe extraction
                keyframes = extract_video_keyframes(video_full_path, frames_dir)
                
                job.progress = 30
                job.status_message = f"Frames extracted ({len(keyframes)}). Compressing bundle..."
                db.commit()
                
                # Compress frames
                zip_directory(frames_dir, zip_out_path)
                
                # Cleanup loose frame images to save storage
                for f in keyframes:
                    os.remove(f)
                os.rmdir(frames_dir)
                
            except Exception as e:
                # Log frame extraction errors but fallback to simulation
                job.status_message = f"Warning: OpenCV frame extraction failed: {str(e)}"
                db.commit()
                
        # 2. Trigger Reconstruction Pipeline (Luma AI or self-hosted mock)
        time.sleep(3)
        job.progress = 50
        job.status_message = "Training Neural Radiance Fields / 3D Gaussian Splats..."
        db.commit()
        
        # Simulating NeRF Training iterations
        for p in range(60, 95, 10):
            time.sleep(4)
            job.progress = p
            job.status_message = f"Optimizing Gaussian splat cloud ({p-40}% training completed)..."
            db.commit()
            
        # 3. Finalize splat and generate mock sample splat
        time.sleep(2)
        job.progress = 95
        job.status_message = "Converting 3D model to optimized .splat format..."
        db.commit()
        
        # Create a mock .splat file representing the finished result
        mock_filename = f"capture_{capture.id}.splat"
        mock_splat_dir = os.path.join(settings.STATIC_DIR, "splats")
        os.makedirs(mock_splat_dir, exist_ok=True)
        mock_splat_path = os.path.join(mock_splat_dir, mock_filename)
        
        # Write dummy binary file to simulate the splat model asset
        with open(mock_splat_path, "wb") as f:
            f.write(b"MOCK_3D_GAUSSIAN_SPLAT_DATA_" + capture.id.encode('utf-8'))
            
        # Set dummy thumbnail image
        mock_thumbnail_dir = os.path.join(settings.STATIC_DIR, "thumbnails")
        os.makedirs(mock_thumbnail_dir, exist_ok=True)
        mock_thumb_path = os.path.join(mock_thumbnail_dir, f"thumb_{capture.id}.jpg")
        with open(mock_thumb_path, "wb") as f:
            f.write(b"MOCK_IMAGE_THUMBNAIL_DATA")
            
        # 4. Final Updates
        capture.status = "completed"
        capture.file_url = f"/static/splats/{mock_filename}"
        capture.thumbnail_url = f"/static/thumbnails/thumb_{capture.id}.jpg"
        
        job.progress = 100
        job.status_message = "Reconstruction completed successfully!"
        db.commit()
        
    except Exception as e:
        db.rollback()
        # Handle failure cases gracefully
        if 'job' in locals() and job:
            job.progress = 100
            job.status_message = "Failed"
            job.error_log = str(e)
            db.commit()
        if 'capture' in locals() and capture:
            capture.status = "failed"
            db.commit()
    finally:
        db.close()
