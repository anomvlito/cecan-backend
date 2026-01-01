"""
Database session management for CECAN Platform
Provides database connection and session handling
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import SQLALCHEMY_DATABASE_URL

# Configure connection args
connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Create engine
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency function to get database session.
    Use with FastAPI Depends().
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """
    Get a new database session (non-dependency version).
    Remember to close it after use.
    
    Returns:
        Database session
    """
    return SessionLocal()
