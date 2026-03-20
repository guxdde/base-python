from fastapi import APIRouter
from .config import router as config_router
from .health import router as health_router
from .tasks import router as tasks_router
from .pdf import router as pdf_router
# from .dead_letter import router as dead_letter_router
router = APIRouter()

router.include_router(config_router, prefix="/config")
router.include_router(health_router, prefix="/health")
router.include_router(tasks_router, prefix="/tasks")
router.include_router(pdf_router, prefix="/pdf")
# router.include_router(dead_letter_router, prefix="/dead-letters")
