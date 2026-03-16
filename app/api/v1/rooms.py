from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.repositories.room_repo import RoomRepository
from app.schemas.room_schema import RoomCreate, RoomUpdate, RoomResponse

router = APIRouter()


def get_room_repository(db: Session = Depends(get_db)) -> RoomRepository:
    """Dependency to get room repository"""
    return RoomRepository(db)


@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    room_data: RoomCreate,
    room_repo: RoomRepository = Depends(get_room_repository)
):
    """Create a new room"""
    try:
        room = room_repo.create(room_data)
        return room
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create room"
        )


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: UUID,
    room_repo: RoomRepository = Depends(get_room_repository)
):
    """Get room by ID"""
    room = room_repo.get_by_id(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )
    return room


@router.get("/listing/{listing_id}", response_model=List[RoomResponse])
async def get_rooms_by_listing(
    listing_id: UUID,
    room_repo: RoomRepository = Depends(get_room_repository)
):
    """Get all rooms for a specific listing"""
    rooms = room_repo.get_by_listing(listing_id)
    return rooms


@router.put("/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: UUID,
    room_data: RoomUpdate,
    room_repo: RoomRepository = Depends(get_room_repository)
):
    """Update room by ID"""
    room = room_repo.update(room_id, room_data)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )
    return room


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: UUID,
    room_repo: RoomRepository = Depends(get_room_repository)
):
    """Delete room by ID"""
    success = room_repo.delete(room_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )