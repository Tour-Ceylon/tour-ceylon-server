from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.user import User
from app.models.enum import UserRole
from app.schemas.user_schema import UserCreate, UserUpdate, UserSearchParams


class UserRepository:
    """Repository class for User model database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, user_data: UserCreate) -> User:
        """Create a new user and ensure Clerk user exists"""
        clerk_id = user_data.clerk_user_id
        if not clerk_id:
            try:
                from app.core.auth.clerk import create_clerk_user
                role_val = user_data.role.value if hasattr(user_data.role, "value") else str(user_data.role)
                clerk_id = create_clerk_user(
                    email=user_data.email,
                    password=getattr(user_data, "password", None),
                    full_name=user_data.full_name,
                    role=role_val,
                    vendor_status=getattr(user_data, "vendor_status", None),
                    approved_categories=getattr(user_data, "approved_categories", None),
                    company_name=getattr(user_data, "company_name", None),
                )
            except Exception as e:
                pass

        db_user = User(
            clerk_user_id=clerk_id,
            email=user_data.email,
            full_name=user_data.full_name,
            country=user_data.country,
            role=user_data.role,
            is_active=user_data.is_active,
            vendor_status=getattr(user_data, "vendor_status", None),
            approved_categories=getattr(user_data, "approved_categories", []),
            company_name=getattr(user_data, "company_name", None),
            business_profile=getattr(user_data, "business_profile", {})
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()

    def get_by_clerk_user_id(self, clerk_user_id: str) -> Optional[User]:
        """Get user by Clerk user ID"""
        return self.db.query(User).filter(User.clerk_user_id == clerk_user_id).first()
    
    def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> List[User]:
        """Get all users with optional filtering"""
        query = self.db.query(User)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
            
        return query.offset(skip).limit(limit).all()
    
    def search(self, search_params: UserSearchParams) -> tuple[List[User], int]:
        """Search users with filters and pagination"""
        query = self.db.query(User)
        
        # Apply filters
        filters = []
        
        if search_params.email:
            filters.append(User.email.ilike(f"%{search_params.email}%"))
        
        if search_params.role:
            filters.append(User.role == search_params.role)
        
        if search_params.country:
            filters.append(User.country.ilike(f"%{search_params.country}%"))
        
        if search_params.is_active is not None:
            filters.append(User.is_active == search_params.is_active)

        if search_params.vendor_status:
            filters.append(User.vendor_status == search_params.vendor_status)
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        skip = (search_params.page - 1) * search_params.per_page
        users = query.offset(skip).limit(search_params.per_page).all()
        
        return users, total_count
    
    def update(self, user_id: UUID, user_data: UserUpdate) -> Optional[User]:
        """Update user by ID"""
        db_user = self.get_by_id(user_id)
        if not db_user:
            return None
        
        # Update only provided fields
        update_data = user_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def delete(self, user_id: UUID) -> bool:
        """Delete user by ID"""
        db_user = self.get_by_id(user_id)
        if not db_user:
            return False
        
        self.db.delete(db_user)
        self.db.commit()
        return True
    
    def soft_delete(self, user_id: UUID) -> Optional[User]:
        """Soft delete user by setting is_active to False"""
        db_user = self.get_by_id(user_id)
        if not db_user:
            return None
        
        db_user.is_active = False
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def activate(self, user_id: UUID) -> Optional[User]:
        """Activate user by setting is_active to True"""
        db_user = self.get_by_id(user_id)
        if not db_user:
            return None
        
        db_user.is_active = True
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def get_by_role(self, role: UserRole) -> List[User]:
        """Get all users by role"""
        return self.db.query(User).filter(User.role == role).all()
    
    def get_by_country(self, country: str) -> List[User]:
        """Get all users by country"""
        return self.db.query(User).filter(User.country.ilike(f"%{country}%")).all()
    
    def count_by_role(self) -> dict:
        """Get user count grouped by role"""
        results = (
            self.db.query(User.role, func.count(User.id))
            .group_by(User.role)
            .all()
        )
        return {role: count for role, count in results}
    
    def count_active_users(self) -> int:
        """Get count of active users"""
        return self.db.query(User).filter(User.is_active == True).count()

    def count_inactive_users(self) -> int:
        """Get count of inactive users"""
        return self.db.query(User).filter(User.is_active == False).count()
    
    def exists_by_email(self, email: str, exclude_user_id: Optional[UUID] = None) -> bool:
        """Check if user exists by email, optionally excluding a specific user ID"""
        query = self.db.query(User).filter(User.email == email)
        
        if exclude_user_id:
            query = query.filter(User.id != exclude_user_id)

        return query.first() is not None

    def count_all(self, is_active: Optional[bool] = None) -> int:
        query = self.db.query(func.count(User.id))
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        return query.scalar() or 0


# Dependency function to get user repository
def get_user_repository(db: Session = None) -> UserRepository:
    """Get user repository instance"""
    if db is None:
        from app.config.database import SessionLocal
        db = SessionLocal()
    return UserRepository(db)
