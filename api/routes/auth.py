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
from core.models import User, UserRole, AcademicMember, ResearcherDetails
from core.security import get_current_user, oauth2_scheme
from sqlalchemy.orm import joinedload
from schemas import UserMeResponse, UserBasicInfo, AcademicMemberContext, WorkPackageSchema

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


@router.get("/me", response_model=UserMeResponse)
async def read_users_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete user context including academic member information.

    This endpoint is the "source of truth" for the frontend to understand:
    - Who is logged in (user account info)
    - What is their organizational identity (academic member)
    - What permissions they have (role + category + WPs)

    Returns:
        UserMeResponse with user and academic_member data
    """
    # Build basic user info
    user_info = UserBasicInfo(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        full_name=current_user.full_name
    )

    # Try to find associated academic member (by email match)
    academic_member = db.query(AcademicMember).filter_by(
        email=current_user.email
    ).options(
        joinedload(AcademicMember.researcher_details),
        joinedload(AcademicMember.wps)
    ).first()

    member_context = None
    if academic_member:
        # Get researcher category if applicable
        category = None
        if academic_member.researcher_details:
            category = academic_member.researcher_details.category

        # Build WP list
        wps = []
        if academic_member.wps:
            wps = [
                WorkPackageSchema(id=wp.id, name=wp.name)
                for wp in academic_member.wps
            ]

        member_context = AcademicMemberContext(
            id=academic_member.id,
            full_name=academic_member.full_name,
            member_type=academic_member.member_type,
            category=category,
            wps=wps
        )

    return UserMeResponse(
        user=user_info,
        academic_member=member_context
    )
