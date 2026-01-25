"""
Users API Routes
Simple endpoint to list assignable users
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from core.security import get_current_user
from core.models import User, UserRole
from database.session import get_db

router = APIRouter(prefix="/users", tags=["Users"])


class AssignableUserResponse(BaseModel):
    """User info for assignment purposes."""
    id: int
    full_name: str
    email: str
    role: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[AssignableUserResponse])
async def get_assignable_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get users that can be assigned to activities.

    Returns users with roles: researcher, staff, student
    """
    users = db.query(User).filter(
        User.role.in_([UserRole.RESEARCHER, UserRole.STAFF, UserRole.STUDENT])
    ).all()

    return [
        AssignableUserResponse(
            id=u.id,
            full_name=u.full_name or u.email.split('@')[0],
            email=u.email,
            role=u.role.value
        )
        for u in users
    ]
