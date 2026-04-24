from sqlalchemy.orm import Session

from app.models.admin_dashboard import AdminSettings


class AdminSettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self) -> AdminSettings:
        settings = self.db.query(AdminSettings).first()
        if settings:
            return settings

        settings = AdminSettings()
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def update(self, settings: AdminSettings, updates: dict) -> AdminSettings:
        for field, value in updates.items():
            setattr(settings, field, value)
        self.db.commit()
        self.db.refresh(settings)
        return settings


