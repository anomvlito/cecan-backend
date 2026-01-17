"""
External Metrics Routes Package

This package contains routes for external API integrations:
- journals.py: WOS Mirror and OpenAlex journal search
- dois.py: DOI listing, extraction, auditing and repair
- analysis.py: AI-powered journal analysis and data triangulation
"""

from fastapi import APIRouter

from .journals import router as journals_router
from .dois import router as dois_router
from .analysis import router as analysis_router

# Create unified router that includes all sub-routers
router = APIRouter(tags=["External Metrics"])

router.include_router(journals_router)
router.include_router(dois_router)
router.include_router(analysis_router)
