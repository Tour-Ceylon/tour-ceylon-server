from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.repositories.transfer_repo import TransferRepository
from app.schemas.transfer_schema import TransferCreate, TransferResponse

router = APIRouter()


def get_transfer_repository(db: Session = Depends(get_db)) -> TransferRepository:
    """Dependency to get transfer repository"""
    return TransferRepository(db)


@router.post("/", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    transfer_data: TransferCreate,
    transfer_repo: TransferRepository = Depends(get_transfer_repository)
):
    """Create a new transfer"""
    try:
        transfer = transfer_repo.create(transfer_data)
        return transfer
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create transfer"
        )


@router.get("/listing/{listing_id}", response_model=TransferResponse)
async def get_transfer_by_listing(
    listing_id: UUID,
    transfer_repo: TransferRepository = Depends(get_transfer_repository)
):
    """Get transfer by listing ID"""
    transfer = transfer_repo.get_by_listing(listing_id)
    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer not found for this listing"
        )
    return transfer