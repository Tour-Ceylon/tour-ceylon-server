from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.media import MediaAsset


class MediaRepository:
    """Database access helpers for media assets."""

    def __init__(self, db: Session):
        self.db = db

    def create_media(self, **kwargs) -> MediaAsset:
        media = MediaAsset(**kwargs)
        self.db.add(media)
        self.db.flush()
        return media

    def get_media_by_id(self, media_id: UUID) -> MediaAsset | None:
        return self.db.query(MediaAsset).filter(MediaAsset.id == media_id).first()

    def list_by_owner(self, owner_type, owner_id: UUID) -> list[MediaAsset]:
        return (
            self.db.query(MediaAsset)
            .filter(
                MediaAsset.owner_type == owner_type,
                MediaAsset.owner_id == owner_id,
            )
            .order_by(MediaAsset.sort_order.asc(), MediaAsset.created_at.asc())
            .all()
        )

    def delete_media(self, media: MediaAsset) -> None:
        self.db.delete(media)
        self.db.flush()

    def clear_primary(self, owner_type, owner_id: UUID) -> None:
        (
            self.db.query(MediaAsset)
            .filter(
                MediaAsset.owner_type == owner_type,
                MediaAsset.owner_id == owner_id,
                MediaAsset.is_primary.is_(True),
            )
            .update({"is_primary": False}, synchronize_session=False)
        )
        self.db.flush()

    def set_primary(self, media_id: UUID) -> MediaAsset | None:
        media = self.get_media_by_id(media_id)
        if media is None:
            return None
        media.is_primary = True
        self.db.flush()
        return media

    def update_sort_orders(self, owner_type, owner_id: UUID, updates: list[tuple[UUID, int]]) -> list[MediaAsset]:
        if not updates:
            return self.list_by_owner(owner_type, owner_id)

        media_items = {
            media.id: media
            for media in self.list_by_owner(owner_type, owner_id)
        }
        for media_id, sort_order in updates:
            media = media_items.get(media_id)
            if media is not None:
                media.sort_order = sort_order
        self.db.flush()
        return self.list_by_owner(owner_type, owner_id)

    def get_cover_media(self, owner_type, owner_id: UUID) -> MediaAsset | None:
        return (
            self.db.query(MediaAsset)
            .filter(
                MediaAsset.owner_type == owner_type,
                MediaAsset.owner_id == owner_id,
                MediaAsset.is_primary.is_(True),
            )
            .order_by(MediaAsset.sort_order.asc(), MediaAsset.created_at.asc())
            .first()
        )

    def get_next_cover_candidate(
        self,
        owner_type,
        owner_id: UUID,
        exclude_media_id: UUID | None = None,
    ) -> MediaAsset | None:
        query = (
            self.db.query(MediaAsset)
            .filter(
                MediaAsset.owner_type == owner_type,
                MediaAsset.owner_id == owner_id,
            )
        )
        if exclude_media_id is not None:
            query = query.filter(MediaAsset.id != exclude_media_id)
        return query.order_by(MediaAsset.sort_order.asc(), MediaAsset.created_at.asc()).first()
