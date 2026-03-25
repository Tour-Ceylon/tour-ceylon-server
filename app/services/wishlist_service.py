import logging
from uuid import UUID

from fastapi import HTTPException, status

from app.integrations.supabase_client import get_supabase_client, get_supabase_rls_client


VALID_ITEM_TYPES = {"tour_package", "destination"}
ITEM_TABLE_BY_TYPE = {
    "tour_package": "Packages",
    "destination": "Listings",
}
logger = logging.getLogger("app.wishlist")


def _as_uuid_str(value: str, field_name: str) -> str:
    try:
        return str(UUID(str(value)))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID for {field_name}",
        ) from exc


def _validate_item_type(item_type: str) -> str:
    normalized = str(item_type).strip().lower()
    if normalized not in VALID_ITEM_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="item_type must be either 'tour_package' or 'destination'",
        )
    return normalized


def _resolve_client(user_id: str, supabase_access_token: str | None):
    if supabase_access_token:
        return get_supabase_client(user_access_token=supabase_access_token)
    return get_supabase_rls_client(user_id)


def _ensure_item_exists(item_id: str, item_type: str, user_id: str, supabase_access_token: str | None) -> None:
    table_name = ITEM_TABLE_BY_TYPE[item_type]
    res = (
        _resolve_client(user_id, supabase_access_token)
        .table(table_name)
        .select("id")
        .eq("id", item_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{item_type} item not found",
        )


def toggle_wishlist(
    user_id: str,
    item_id: str,
    item_type: str,
    supabase_access_token: str | None = None,
) -> dict:
    validated_user_id = _as_uuid_str(user_id, "user_id")
    validated_item_id = _as_uuid_str(item_id, "item_id")
    validated_item_type = _validate_item_type(item_type)
    _ensure_item_exists(
        validated_item_id,
        validated_item_type,
        validated_user_id,
        supabase_access_token,
    )

    client = _resolve_client(validated_user_id, supabase_access_token)

    existing = (
        client
        .table("wishlists")
        .select("id")
        .eq("user_id", validated_user_id)
        .eq("item_id", validated_item_id)
        .eq("item_type", validated_item_type)
        .limit(1)
        .execute()
    )

    if existing.data:
        (
            client
            .table("wishlists")
            .delete()
            .eq("user_id", validated_user_id)
            .eq("item_id", validated_item_id)
            .eq("item_type", validated_item_type)
            .execute()
        )
        logger.info(
            "wishlist.removed user_id=%s item_id=%s item_type=%s",
            validated_user_id,
            validated_item_id,
            validated_item_type,
        )
        return {"status": "removed"}

    (
        client
        .table("wishlists")
        .insert(
            {
                "user_id": validated_user_id,
                "item_id": validated_item_id,
                "item_type": validated_item_type,
            }
        )
        .execute()
    )
    logger.info(
        "wishlist.added user_id=%s item_id=%s item_type=%s",
        validated_user_id,
        validated_item_id,
        validated_item_type,
    )
    return {"status": "added"}


def is_wishlisted(
    user_id: str,
    item_id: str,
    item_type: str,
    supabase_access_token: str | None = None,
) -> bool:
    validated_user_id = _as_uuid_str(user_id, "user_id")
    validated_item_id = _as_uuid_str(item_id, "item_id")
    validated_item_type = _validate_item_type(item_type)

    client = _resolve_client(validated_user_id, supabase_access_token)
    res = (
        client
        .table("wishlists")
        .select("id")
        .eq("user_id", validated_user_id)
        .eq("item_id", validated_item_id)
        .eq("item_type", validated_item_type)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def get_wishlist(user_id: str, supabase_access_token: str | None = None) -> list[dict]:
    validated_user_id = _as_uuid_str(user_id, "user_id")
    client = _resolve_client(validated_user_id, supabase_access_token)
    res = (
        client
        .table("wishlists")
        .select("*")
        .eq("user_id", validated_user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def get_full_wishlist(user_id: str, supabase_access_token: str | None = None) -> dict:
    validated_user_id = _as_uuid_str(user_id, "user_id")
    wishlist = get_wishlist(validated_user_id, supabase_access_token=supabase_access_token)
    package_ids = [item["item_id"] for item in wishlist if item["item_type"] == "tour_package"]
    destination_ids = [item["item_id"] for item in wishlist if item["item_type"] == "destination"]

    packages = []
    destinations = []

    client = _resolve_client(validated_user_id, supabase_access_token)

    if package_ids:
        packages = (
            client
            .table("Packages")
            .select("*")
            .in_("id", package_ids)
            .execute()
            .data
            or []
        )

    if destination_ids:
        destinations = (
            client
            .table("Listings")
            .select("*")
            .in_("id", destination_ids)
            .execute()
            .data
            or []
        )

    return {
        "packages": packages,
        "destinations": destinations,
    }
