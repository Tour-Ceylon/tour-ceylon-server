from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.transferDetail import TransferDetail
from app.schemas.transfer_schema import TransferCreate


class TransferRepository:
    """Deprecated compatibility repository backed by TransferDetail."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, transfer_data: TransferCreate) -> TransferDetail:
        transfer = TransferDetail(**transfer_data.model_dump())
        self.db.add(transfer)
        self.db.commit()
        self.db.refresh(transfer)
        return transfer

    def get_by_listing(self, listing_id: UUID) -> Optional[TransferDetail]:
        return (
            self.db.query(TransferDetail)
            .filter(TransferDetail.listing_id == listing_id)
            .first()
        )
