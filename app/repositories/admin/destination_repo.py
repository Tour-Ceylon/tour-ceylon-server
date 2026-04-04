from sqlalchemy.orm import Session

from app.models.destination import Destination


class AdminDestinationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_active(self) -> list[Destination]:
        return (
            self.db.query(Destination)
            .filter(Destination.is_active.is_(True))
            .order_by(Destination.name.asc(), Destination.id.asc())
            .all()
        )
