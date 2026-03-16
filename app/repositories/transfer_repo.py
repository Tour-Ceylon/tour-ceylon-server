from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.transfer import Transfer
from app.schemas.transfer_schema import TransferCreate


class TransferRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, transfer_data: TransferCreate):

        transfer = Transfer(**transfer_data.model_dump())

        self.db.add(transfer)
        self.db.commit()
        self.db.refresh(transfer)

        return transfer

    def get_by_listing(self, listing_id: UUID) -> Optional[Transfer]:

        return (
            self.db.query(Transfer)
            .filter(Transfer.listing_id == listing_id)
            .first()
        )