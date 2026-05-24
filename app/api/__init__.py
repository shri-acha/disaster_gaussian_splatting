from fastapi import APIRouter
from app.api.endpoints import splats, jobs

api_router = APIRouter()

# Register API endpoints
api_router.include_router(splats.router, prefix="/splats", tags=["splats"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
