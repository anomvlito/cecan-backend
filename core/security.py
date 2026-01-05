
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database.session import get_db

from core.models import User, UserRole
from services.auth_service import AuthService
from utils.security import decode_token

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login") # Updated path to match API prefix if needed, usually just /auth/login but checking router prefix

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Raises:
        HTTPException: If token is invalid or user not found
    
    Returns:
        User object
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    
    auth_service = AuthService(db)
    user = auth_service.get_user_by_email(email)
    
    if user is None:
        raise credentials_exception
    
    return user


# Role-based access control helpers
class RoleChecker:
    """Dependency class to check user roles"""
    
    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, current_user: User = Depends(get_current_user)):
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for your role"
            )
        return current_user


# Pre-configured role checkers
require_admin = RoleChecker([UserRole.ADMIN])
require_editor = RoleChecker([UserRole.ADMIN, UserRole.EDITOR])
require_viewer = RoleChecker([UserRole.ADMIN, UserRole.EDITOR, UserRole.VIEWER])
