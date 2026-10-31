from fastapi import APIRouter

from app.business.order_management.api.manage import router as manage_router

router = APIRouter()
router.include_router(manage_router)
