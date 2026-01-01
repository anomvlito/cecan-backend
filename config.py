"""
Configuration management for CECAN Platform
Centralized settings and environment variables
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Database
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "cecan.db"))
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
else:
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Security
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION_USE_ENV")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60 * 24  # 24 hours

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# CORS
CORS_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",  # Next.js dev server
    "http://127.0.0.1:3000",
]

# Application
APP_TITLE = "CECAN Platform API"
APP_VERSION = "3.1.0"
APP_DESCRIPTION = "Professional SaaS platform for cancer research management"

# Standardized Paths
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# OpenAlex API Configuration
OPENALEX_CONTACT_EMAIL = os.getenv("OPENALEX_EMAIL", "contacto@cecan.cl")
OPENALEX_SYNC_THRESHOLD_DAYS = 30  # Only sync if last sync was >30 days ago
