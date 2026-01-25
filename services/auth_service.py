"""
Authentication Service for CECAN Platform
Business logic for user authentication and authorization
"""

from datetime import timedelta
from typing import Optional
from sqlalchemy.orm import Session

from core.models import User, UserRole
from utils.security import (
    verify_password,
    get_password_hash,
    create_access_token
)
from config import JWT_EXPIRATION_MINUTES


class AuthService:
    """Service for authentication operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user by email and password.
        
        Args:
            email: User email
            password: Plain text password
        
        Returns:
            User object if valid, None otherwise
        """
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    def create_user(self, email: str, password: str, full_name: str = None,
                    role = UserRole.VIEWER) -> User:
        """
        Create a new user.

        Args:
            email: User email
            password: Plain text password
            full_name: Optional full name
            role: User role (can be string or UserRole enum, default: VIEWER)

        Returns:
            Created User object
        """
        hashed_password = get_password_hash(password)

        # Convert string role to UserRole enum if needed
        if isinstance(role, str):
            # Try to find the enum by value (e.g., "pi" -> UserRole.PI)
            role_enum = None
            for role_option in UserRole:
                if role_option.value == role:
                    role_enum = role_option
                    break

            if role_enum is None:
                raise ValueError(f"Invalid role: {role}. Must be one of: {[r.value for r in UserRole]}")

            role = role_enum

        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role  # SQLAlchemy will use the enum's .value (e.g., "pi") thanks to values_callable
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def generate_token(self, user: User) -> str:
        """
        Generate JWT token for user.
        
        Args:
            user: User object
        
        Returns:
            JWT token string
        """
        access_token_expires = timedelta(minutes=JWT_EXPIRATION_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )
        return access_token
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email and attach academic_member if exists.

        This is critical for authorization checks that need member_id.
        """
        from core.models import AcademicMember

        user = self.db.query(User).filter(User.email == email).first()

        if user:
            # Manually load academic_member by email match
            academic_member = self.db.query(AcademicMember).filter_by(
                email=user.email
            ).first()

            # Attach as attribute (not a real relationship, but works for authz)
            user._academic_member = academic_member

        return user
