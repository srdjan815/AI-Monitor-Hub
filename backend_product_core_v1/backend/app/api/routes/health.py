from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()

@router.get("/")
async def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "version": settings.app_version
    }
