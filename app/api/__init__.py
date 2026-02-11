# API package for OpenCode MVP framework
from fastapi import APIRouter
from .config import router as config_router
from .health import router as health_router
router = APIRouter()

router.include_router(config_router, prefix="/config")
router.include_router(health_router, prefix="/health")
