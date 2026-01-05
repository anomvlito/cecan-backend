"""
CECAN Platform - Main Application Entry Point
Professional SaaS platform for cancer research management
Clean Architecture with modular design
"""
import config
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from config import APP_TITLE, APP_VERSION, APP_DESCRIPTION, CORS_ORIGINS
from api.routes import auth, compliance, publications, researchers, rag, dashboard, members, files, reports, public, catalogs, external, students

# Create FastAPI application
app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(compliance.router, prefix="/api")
app.include_router(publications.router, prefix="/api")
app.include_router(researchers.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(public.router, prefix="/api")
app.include_router(catalogs.router, prefix="/api")
app.include_router(external.router, prefix="/api/external")
app.include_router(students.router, prefix="/api")

# Static files and frontend
# Mount this LAST to avoid overriding API routes
# app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "service": "CECAN Platform API"
    }


@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "title": APP_TITLE,
        "version": APP_VERSION,
        "description": APP_DESCRIPTION,
        "endpoints": {
            "auth": "/api/auth",
            "compliance": "/api/compliance",
            "publications": "/api/publications",
            "researchers": "/api/researchers",
            "rag": "/api/rag"
        },
        "docs": "/docs",
        "redoc": "/redoc"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Force server reload: UnboundLocalError fix
