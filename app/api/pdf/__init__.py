from fastapi import APIRouter
from .pdf import router as pdf_router
router = APIRouter()

router.include_router(pdf_router, tags=["pdf"])
