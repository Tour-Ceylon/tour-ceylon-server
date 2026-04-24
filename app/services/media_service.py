from __future__ import annotations

from uuid import UUID

from fastapi import UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.errors import AdminAPIError
from app.integrations.cloudinary import CloudinaryIntegrationError, delete_image, upload_image
from app.models.enum import MediaOwnerType
from app.repositories.admin.package_repo import AdminPackageRepository
from app.repositories.listing_repo import ListingRepository
from app.repositories.media_repo import MediaRepository


class MediaService:
    """Business logic for Cloudinary-backed listing and package media."""

    ALLOWED_CONTENT_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

    def __init__(self, db: Session):
        self.db = db
        self.media_repo = MediaRepository(db)
        self.listing_repo = ListingRepository(db)
        self.package_repo = AdminPackageRepository(db)

    def upload_listing_media(
        self,
        listing_id: UUID,
        files: list[UploadFile],
        alt_texts: list[str] | None = None,
        is_primary: bool = False,
        sort_orders: list[int] | None = None,
    ) -> dict:
        listing = self._get_listing(listing_id)
        self._upload_media(
            owner_type=MediaOwnerType.LISTING,
            owner=listing,
            files=files,
            alt_texts=alt_texts,
            is_primary=is_primary,
            sort_orders=sort_orders,
        )
        return self._build_owner_response(listing)

    def upload_package_media(
        self,
        package_id: UUID,
        files: list[UploadFile],
        alt_texts: list[str] | None = None,
        is_primary: bool = False,
        sort_orders: list[int] | None = None,
    ) -> dict:
        package = self._get_package(package_id)
        self._upload_media(
            owner_type=MediaOwnerType.PACKAGE,
            owner=package,
            files=files,
            alt_texts=alt_texts,
            is_primary=is_primary,
            sort_orders=sort_orders,
        )
        return self._build_owner_response(package)

    def list_owner_media(self, owner_type: MediaOwnerType, owner_id: UUID) -> dict:
        owner = self._get_owner(owner_type, owner_id)
        return self._build_owner_response(owner)

    def set_primary(self, owner_type: MediaOwnerType, owner_id: UUID, media_id: UUID) -> dict:
        owner = self._get_owner(owner_type, owner_id)
        media = self._get_owner_media_or_404(owner_type, owner_id, media_id)

        try:
            self.media_repo.clear_primary(owner_type, owner_id)
            self.media_repo.set_primary(media.id)
            self._update_owner_cover(owner_type, owner, media.id)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise AdminAPIError(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update primary media") from exc

        refreshed_owner = self._get_owner(owner_type, owner_id)
        return self._build_owner_response(refreshed_owner)

    def reorder(self, owner_type: MediaOwnerType, owner_id: UUID, reorder_items) -> dict:
        owner = self._get_owner(owner_type, owner_id)
        media_items = self.media_repo.list_by_owner(owner_type, owner_id)
        media_ids = {media.id for media in media_items}
        requested_ids = {item.id for item in reorder_items}
        if requested_ids != media_ids:
            raise AdminAPIError(status.HTTP_400_BAD_REQUEST, "Reorder request must include all owner media IDs")

        try:
            self.media_repo.update_sort_orders(
                owner_type,
                owner_id,
                [(item.id, item.sort_order) for item in reorder_items],
            )
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise AdminAPIError(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to reorder media") from exc

        refreshed_owner = self._get_owner(owner_type, owner_id)
        return self._build_owner_response(refreshed_owner)

    def delete_media(self, owner_type: MediaOwnerType, owner_id: UUID, media_id: UUID) -> dict:
        owner = self._get_owner(owner_type, owner_id)
        media = self._get_owner_media_or_404(owner_type, owner_id, media_id)
        next_cover = None

        if not self._is_legacy_public_id(media.cloudinary_public_id):
            try:
                delete_image(media.cloudinary_public_id)
            except CloudinaryIntegrationError as exc:
                raise AdminAPIError(status.HTTP_502_BAD_GATEWAY, "Failed to delete media from Cloudinary") from exc

        try:
            was_cover = media.is_primary or getattr(owner, "cover_media_id", None) == media.id
            self.media_repo.delete_media(media)
            if was_cover:
                next_cover = self.media_repo.get_next_cover_candidate(owner_type, owner_id, exclude_media_id=media_id)
                self.media_repo.clear_primary(owner_type, owner_id)
                if next_cover is not None:
                    self.media_repo.set_primary(next_cover.id)
                    self._update_owner_cover(owner_type, owner, next_cover.id)
                else:
                    self._update_owner_cover(owner_type, owner, None)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise AdminAPIError(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to delete media") from exc

        refreshed_owner = self._get_owner(owner_type, owner_id)
        return self._build_owner_response(refreshed_owner)

    def _upload_media(
        self,
        owner_type: MediaOwnerType,
        owner,
        files: list[UploadFile],
        alt_texts: list[str] | None,
        is_primary: bool,
        sort_orders: list[int] | None,
    ) -> None:
        if not files:
            raise AdminAPIError(status.HTTP_400_BAD_REQUEST, "At least one file is required")

        normalized_alt_texts = self._normalize_alt_texts(files, alt_texts)
        normalized_sort_orders = self._normalize_sort_orders(files, sort_orders, owner_type, owner.id)
        uploaded_public_ids: list[str] = []
        folder = self._build_folder(owner_type, owner.id)
        existing_cover = self.media_repo.get_cover_media(owner_type, owner.id)

        try:
            for index, upload in enumerate(files):
                file_bytes = self._read_and_validate_file(upload)
                cloudinary_result = upload_image(file_bytes, folder=folder)
                uploaded_public_ids.append(cloudinary_result["public_id"])

                make_primary = False
                if index == 0 and (is_primary or existing_cover is None):
                    make_primary = True

                if make_primary:
                    self.media_repo.clear_primary(owner_type, owner.id)

                media = self.media_repo.create_media(
                    owner_type=owner_type,
                    owner_id=owner.id,
                    cloudinary_public_id=cloudinary_result["public_id"],
                    secure_url=cloudinary_result["secure_url"],
                    resource_type=cloudinary_result.get("resource_type", "image"),
                    format=cloudinary_result.get("format"),
                    width=cloudinary_result.get("width"),
                    height=cloudinary_result.get("height"),
                    bytes=cloudinary_result.get("bytes"),
                    alt_text=normalized_alt_texts[index],
                    sort_order=normalized_sort_orders[index],
                    is_primary=make_primary,
                )
                if make_primary:
                    self._update_owner_cover(owner_type, owner, media.id)

            self.db.commit()
        except CloudinaryIntegrationError as exc:
            self.db.rollback()
            self._cleanup_uploaded_assets(uploaded_public_ids)
            raise AdminAPIError(status.HTTP_502_BAD_GATEWAY, "Failed to upload media to Cloudinary") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            self._cleanup_uploaded_assets(uploaded_public_ids)
            raise AdminAPIError(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to save media") from exc

    def _get_listing(self, listing_id: UUID):
        listing = self.listing_repo.get_by_id(listing_id)
        if listing is None:
            raise AdminAPIError(status.HTTP_404_NOT_FOUND, "Listing not found")
        return listing

    def _get_package(self, package_id: UUID):
        package = self.package_repo.get(package_id)
        if package is None:
            raise AdminAPIError(status.HTTP_404_NOT_FOUND, "Package not found")
        return package

    def _get_owner(self, owner_type: MediaOwnerType, owner_id: UUID):
        if owner_type == MediaOwnerType.LISTING:
            return self._get_listing(owner_id)
        return self._get_package(owner_id)

    def _get_owner_media_or_404(self, owner_type: MediaOwnerType, owner_id: UUID, media_id: UUID):
        media = self.media_repo.get_media_by_id(media_id)
        if media is None or media.owner_type != owner_type or media.owner_id != owner_id:
            raise AdminAPIError(status.HTTP_404_NOT_FOUND, "Media not found")
        return media

    def _read_and_validate_file(self, upload: UploadFile) -> bytes:
        if upload.content_type not in self.ALLOWED_CONTENT_TYPES:
            raise AdminAPIError(status.HTTP_400_BAD_REQUEST, f"Unsupported content type: {upload.content_type}")

        file_bytes = upload.file.read()
        if not file_bytes:
            raise AdminAPIError(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")
        if len(file_bytes) > self.MAX_FILE_SIZE_BYTES:
            raise AdminAPIError(status.HTTP_400_BAD_REQUEST, "Uploaded file exceeds size limit")
        return file_bytes

    def _normalize_alt_texts(self, files: list[UploadFile], alt_texts: list[str] | None) -> list[str | None]:
        if alt_texts is None:
            return [None] * len(files)
        if len(alt_texts) != len(files):
            raise AdminAPIError(status.HTTP_400_BAD_REQUEST, "alt_texts count must match files count")
        return [text or None for text in alt_texts]

    def _normalize_sort_orders(
        self,
        files: list[UploadFile],
        sort_orders: list[int] | None,
        owner_type: MediaOwnerType,
        owner_id: UUID,
    ) -> list[int]:
        if sort_orders is not None:
            if len(sort_orders) != len(files):
                raise AdminAPIError(status.HTTP_400_BAD_REQUEST, "sort_orders count must match files count")
            return sort_orders

        existing_media = self.media_repo.list_by_owner(owner_type, owner_id)
        start = existing_media[-1].sort_order + 1 if existing_media else 0
        return [start + index for index in range(len(files))]

    def _build_folder(self, owner_type: MediaOwnerType, owner_id: UUID) -> str:
        from app.config.settings import settings

        base_folder = (settings.CLOUDINARY_FOLDER or "tour-ceylon").strip("/")
        if owner_type == MediaOwnerType.LISTING:
            return f"{base_folder}/listings/{owner_id}"
        return f"{base_folder}/packages/{owner_id}"

    def _update_owner_cover(self, owner_type: MediaOwnerType, owner, media_id: UUID | None) -> None:
        if owner_type == MediaOwnerType.LISTING:
            self.listing_repo.update_cover_media(owner, media_id)
        else:
            self.package_repo.update_cover_media(owner, media_id)

    def _cleanup_uploaded_assets(self, public_ids: list[str]) -> None:
        for public_id in public_ids:
            try:
                delete_image(public_id)
            except CloudinaryIntegrationError:
                continue

    def _build_owner_response(self, owner) -> dict:
        return {
            "id": owner.id,
            "cover_image": owner.cover_image,
            "gallery": owner.gallery,
        }

    def _is_legacy_public_id(self, public_id: str) -> bool:
        return public_id.startswith("legacy/")
