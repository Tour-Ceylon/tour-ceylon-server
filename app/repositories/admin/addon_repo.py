from uuid import UUID

from sqlalchemy.orm import Session

from app.models.admin_dashboard import AddOn


class AdminAddonRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, name: str, description: str, price: float, category: str) -> AddOn:
        addon = AddOn(
            name=name,
            description=description,
            price=price,
            category=category,
        )
        self.db.add(addon)
        self.db.commit()
        self.db.refresh(addon)
        return addon

    def get_all(self) -> list[AddOn]:
        return self.db.query(AddOn).order_by(AddOn.created_at.desc()).all()

    def get(self, addon_id: UUID) -> AddOn | None:
        return self.db.query(AddOn).filter(AddOn.id == addon_id).first()

    def delete(self, addon_id: UUID) -> bool:
        addon = self.get(addon_id)
        if not addon:
            return False
        self.db.delete(addon)
        self.db.commit()
        return True

    def delete_all(self) -> None:
        self.db.query(AddOn).delete()
        self.db.commit()


