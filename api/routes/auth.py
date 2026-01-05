"""
Authentication Routes for CECAN Platform
API endpoints for login and user management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional


from database.session import get_db
from services.auth_service import AuthService
from core.models import User, UserRole
from core.security import get_current_user, oauth2_scheme

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Schemas
class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    """User information response"""
    id: int
    email: str
    full_name: Optional[str]
    role: UserRole
    
    class Config:
        from_attributes = True


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2 compatible token login.
    Get an access token for future requests.
    """
    auth_service = AuthService(db)
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.generate_token(user)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user
