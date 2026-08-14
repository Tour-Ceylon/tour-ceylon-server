from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import math
import logging
import time

from app.api.deps import get_current_user, get_current_user_with_sync
from app.config.database import get_db
from app.repositories.user_repo import UserRepository
from app.schemas.user_schema import (
    UserCreate, 
    UserUpdate, 
    UserResponse, 
    UserListResponse, 
    UserSearchParams,
    VendorApply
)
from app.models.enum import UserRole
from app.models.user import User
from app.core.auth.clerk import sync_user_metadata_to_clerk

router = APIRouter()
logger = logging.getLogger("app.users")


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """Dependency to get user repository"""
    return UserRepository(db)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Create a new user"""
    
    # Check if user with email already exists
    if user_repo.exists_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    try:
        user = user_repo.create(user_data)
        if user and user.clerk_user_id:
            from app.core.auth.clerk import sync_user_metadata_to_clerk
            sync_user_metadata_to_clerk(
                clerk_user_id=user.clerk_user_id,
                role=user.role.value if hasattr(user.role, "value") else str(user.role),
                vendor_status=user.vendor_status,
                approved_categories=user.approved_categories,
                company_name=user.company_name
            )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get the authenticated local user resolved from Clerk auth."""

    return current_user


@router.post("/sync", response_model=UserResponse)
async def sync_user(
    current_user: User = Depends(get_current_user_with_sync),
):
    """Idempotently resolve or auto-provision the authenticated user."""

    return current_user


@router.post("/apply-vendor", response_model=UserResponse)
async def apply_vendor(
    vendor_data: VendorApply,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a vendor application for the currently logged-in user."""
    current_user.role = UserRole.VENDOR
    current_user.vendor_status = "pending"
    current_user.company_name = vendor_data.business_name
    current_user.approved_categories = vendor_data.categories
    current_user.business_profile = {
        "phone": vendor_data.phone,
        "description": vendor_data.business_description
    }

    try:
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
        
        if current_user.clerk_user_id:
            sync_user_metadata_to_clerk(
                clerk_user_id=current_user.clerk_user_id,
                role="vendor",
                vendor_status="pending",
                approved_categories=vendor_data.categories,
                company_name=vendor_data.business_name
            )
            
        return current_user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply as vendor: {str(e)}"
        )



@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Get user by ID"""
    
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.get("/email/{email}", response_model=UserResponse)
async def get_user_by_email(
    email: str,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Get user by email"""
    
    user = user_repo.get_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.get("/", response_model=UserListResponse)
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    is_active: bool = Query(None),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Get all users with pagination"""
    started_at = time.perf_counter()
    users = user_repo.get_all(skip=skip, limit=limit, is_active=is_active)
    total = user_repo.count_all(is_active=is_active)

    response = UserListResponse(
        users=users,
        total=total,
        page=skip // limit + 1,
        per_page=limit,
        total_pages=math.ceil(total / limit) if total > 0 else 0
    )
    logger.info(
        "users.get_users_timing skip=%s limit=%s is_active=%s result_count=%s total=%s elapsed_ms=%.2f",
        skip,
        limit,
        is_active,
        len(users),
        total,
        (time.perf_counter() - started_at) * 1000,
    )
    return response


@router.post("/search", response_model=UserListResponse)
async def search_users(
    search_params: UserSearchParams,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Search users with filters"""
    started_at = time.perf_counter()
    users, total_count = user_repo.search(search_params)

    response = UserListResponse(
        users=users,
        total=total_count,
        page=search_params.page,
        per_page=search_params.per_page,
        total_pages=math.ceil(total_count / search_params.per_page) if total_count > 0 else 0
    )
    logger.info(
        "users.search_users_timing page=%s per_page=%s role=%s is_active=%s vendor_status=%s email_query=%s result_count=%s total=%s elapsed_ms=%.2f",
        search_params.page,
        search_params.per_page,
        search_params.role,
        search_params.is_active,
        search_params.vendor_status,
        bool(search_params.email),
        len(users),
        total_count,
        (time.perf_counter() - started_at) * 1000,
    )
    return response


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Update user by ID"""
    
    # Check if user exists
    existing_user = user_repo.get_by_id(user_id)
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if email is being updated and already exists
    if user_data.email and user_repo.exists_by_email(user_data.email, exclude_user_id=user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    try:
        updated_user = user_repo.update(user_id, user_data)
        if updated_user and updated_user.clerk_user_id:
            from app.core.auth.clerk import sync_user_metadata_to_clerk
            sync_user_metadata_to_clerk(
                clerk_user_id=updated_user.clerk_user_id,
                role=updated_user.role.value if hasattr(updated_user.role, "value") else str(updated_user.role),
                vendor_status=updated_user.vendor_status,
                approved_categories=updated_user.approved_categories,
                company_name=updated_user.company_name
            )
        return updated_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Delete user by ID (hard delete)"""
    
    success = user_repo.delete(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Deactivate user (soft delete)"""
    
    user = user_repo.soft_delete(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.patch("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Activate user"""
    
    user = user_repo.activate(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.get("/role/{role}", response_model=List[UserResponse])
async def get_users_by_role(
    role: UserRole,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Get all users by role"""
    
    users = user_repo.get_by_role(role)
    return users


@router.get("/country/{country}", response_model=List[UserResponse])
async def get_users_by_country(
    country: str,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Get all users by country"""
    
    users = user_repo.get_by_country(country)
    return users


@router.get("/stats/roles")
async def get_user_role_stats(
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """Get user count statistics by role"""
    
    role_counts = user_repo.count_by_role()
    active_count = user_repo.count_active_users()
    inactive_count = user_repo.count_inactive_users()
    
    return {
        "role_distribution": role_counts,
        "active_users": active_count,
        "inactive_users": inactive_count,
        "total_users": active_count + inactive_count
    }
