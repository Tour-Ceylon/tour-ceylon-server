from __future__ import annotations

from functools import lru_cache

from app.config.settings import settings


class CloudinaryIntegrationError(Exception):
    """Raised when Cloudinary configuration or API operations fail."""


def _load_cloudinary_modules():
    try:
        import cloudinary  # type: ignore
        import cloudinary.uploader  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise CloudinaryIntegrationError("Cloudinary SDK is not installed") from exc
    return cloudinary, cloudinary.uploader


@lru_cache
def configure_cloudinary() -> None:
    if not (
        settings.CLOUDINARY_CLOUD_NAME
        and settings.CLOUDINARY_API_KEY
        and settings.CLOUDINARY_API_SECRET
    ):
        raise CloudinaryIntegrationError("Cloudinary credentials are not fully configured")

    cloudinary, _ = _load_cloudinary_modules()
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


def upload_image(file_bytes: bytes, folder: str, public_id: str | None = None) -> dict:
    """Upload image bytes to Cloudinary and return provider metadata."""

    configure_cloudinary()
    _, cloudinary_uploader = _load_cloudinary_modules()

    options = {
        "folder": folder,
        "resource_type": "image",
        "overwrite": False,
        "secure": True,
    }
    if public_id:
        options["public_id"] = public_id

    try:
        result = cloudinary_uploader.upload(file_bytes, **options)
    except Exception as exc:  # pragma: no cover
        raise CloudinaryIntegrationError("Cloudinary upload failed") from exc

    if not result.get("secure_url") or not result.get("public_id"):
        raise CloudinaryIntegrationError("Cloudinary upload returned incomplete metadata")

    return result


def delete_image(public_id: str) -> None:
    """Delete an image from Cloudinary by public ID."""

    configure_cloudinary()
    _, cloudinary_uploader = _load_cloudinary_modules()

    try:
        cloudinary_uploader.destroy(public_id, resource_type="image")
    except Exception as exc:  # pragma: no cover
        raise CloudinaryIntegrationError("Cloudinary delete failed") from exc
