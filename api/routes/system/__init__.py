"""
System Routes Package - Administrative utilities
"""

from fastapi import APIRouter

from .explorer import router as explorer_router

# Create unified router for system endpoints
router = APIRouter(tags=["System"])

router.include_router(explorer_router)
