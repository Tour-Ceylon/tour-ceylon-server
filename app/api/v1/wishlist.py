from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, get_auth_context
from app.core.rate_limit import enforce_wishlist_toggle_rate_limit
from app.schemas.wishlist_schema import (
    FullWishlistResponse,
    WishlistItemType,
    WishlistStatusResponse,
    WishlistToggleRequest,
    WishlistToggleResponse,
)
from app.services.wishlist_service import get_full_wishlist, is_wishlisted, toggle_wishlist

router = APIRouter()


@router.post("/toggle", response_model=WishlistToggleResponse)
async def toggle(
    payload: WishlistToggleRequest,
    auth_context: AuthContext = Depends(get_auth_context),
):
    enforce_wishlist_toggle_rate_limit(auth_context.user_id)
    return toggle_wishlist(
        user_id=str(auth_context.user_id),
        item_id=str(payload.item_id),
        item_type=payload.item_type.value,
        supabase_access_token=auth_context.supabase_access_token,
    )


@router.get("", response_model=FullWishlistResponse)
async def get(
    auth_context: AuthContext = Depends(get_auth_context),
):
    return get_full_wishlist(
        user_id=str(auth_context.user_id),
        supabase_access_token=auth_context.supabase_access_token,
    )


@router.get("/status", response_model=WishlistStatusResponse)
async def get_status(
    item_id: UUID = Query(...),
    item_type: WishlistItemType = Query(...),
    auth_context: AuthContext = Depends(get_auth_context),
):
    return {
        "is_wishlisted": is_wishlisted(
            user_id=str(auth_context.user_id),
            item_id=str(item_id),
            item_type=item_type.value,
            supabase_access_token=auth_context.supabase_access_token,
        )
    }
