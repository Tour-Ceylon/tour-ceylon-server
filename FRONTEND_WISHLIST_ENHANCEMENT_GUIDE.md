# Frontend Wishlist Enhancement Guide

This document explains how to implement wishlist features on the frontend for the new backend wishlist system.

## 1) Backend Contract Summary

Base API prefix:
- `/api/v1/wishlist`

Endpoints:
1. `POST /api/v1/wishlist/toggle`
   - Body:
   ```json
   {
     "item_id": "uuid",
     "item_type": "tour_package" | "destination"
   }
   ```
   - Response:
   ```json
   { "status": "added" | "removed" }
   ```

2. `GET /api/v1/wishlist`
   - Response:
   ```json
   {
     "packages": [/* rows from Packages */],
     "destinations": [/* rows from Listings */]
   }
   ```

3. `GET /api/v1/wishlist/status?item_id=<uuid>&item_type=<type>`
   - Response:
   ```json
   { "is_wishlisted": true | false }
   ```

Authentication:
- Send Clerk JWT in header:
  - `Authorization: Bearer <token>`
- Backend resolves user from token and linked local user record.
- Do not send `user_id` from frontend.

## 2) Frontend UI Enhancements

Implement wishlist behavior in these places:
1. Package cards/details (`item_type = "tour_package"`).
2. Destination/listing cards/details (`item_type = "destination"`).
3. Dedicated wishlist page/tab showing grouped results:
   - Packages section
   - Destinations section

Wishlist button states:
- Default: outline heart.
- Active: filled heart.
- Loading: disabled with spinner.

Recommended UX:
- Use optimistic toggle for fast UI response.
- If API fails, rollback UI state and show toast.

## 3) API Service Layer (Frontend)

Create a single wishlist API module (example names):
- `getWishlist()`
- `getWishlistStatus(itemId, itemType)`
- `toggleWishlist(itemId, itemType)`

TypeScript types:
```ts
export type WishlistItemType = "tour_package" | "destination";

export type ToggleWishlistResponse = {
  status: "added" | "removed";
};

export type WishlistStatusResponse = {
  is_wishlisted: boolean;
};

export type FullWishlistResponse = {
  packages: any[];
  destinations: any[];
};
```

## 4) State Management Strategy

Recommended keys (React Query/SWR style):
- `["wishlist", "full"]`
- `["wishlist", "status", itemType, itemId]`

On toggle success:
1. Update local card state immediately.
2. Invalidate/revalidate:
   - item status key
   - full wishlist key

On page load:
- For listing grids, either:
  1. bulk-fetch full wishlist and map IDs for icon states, or
  2. lazy-fetch status per visible item.

Use (1) for better performance on pages with many cards.

## 5) Suggested Component Contract

Reusable component props:
```ts
type WishlistButtonProps = {
  itemId: string;
  itemType: "tour_package" | "destination";
  initialWishlisted?: boolean;
  onChange?: (isWishlisted: boolean) => void;
};
```

Behavior:
1. Read initial state from props/cache.
2. On click, call `toggleWishlist`.
3. If response status is:
   - `"added"` => set `true`
   - `"removed"` => set `false`

## 6) Error Handling Rules

Handle these consistently:
1. `401`:
   - Prompt sign-in or redirect to auth.
   - Show: "Please sign in to use wishlist."

2. `400`:
   - Invalid item type/id. Log for debugging; show generic failure toast.

3. `404`:
   - Item not found. Remove/disable wishlist action for that card.

4. `5xx`:
   - Show retry-friendly toast.

## 7) Performance and Scalability Notes

1. Avoid repeated status calls for long lists if full wishlist is already fetched.
2. Debounce rapid repeated clicks (or disable while request in flight).
3. Keep heart toggle interactions idempotent through backend response status.
4. Prefer cache revalidation over full page reload.

## 8) Frontend Implementation Checklist

1. Add wishlist API client methods.
2. Add `WishlistButton` reusable component.
3. Integrate button into:
   - package card
   - package details
   - destination/listing card
   - destination/listing details
4. Add wishlist page with grouped sections.
5. Add auth-aware UX for unauthenticated users.
6. Add loading/optimistic/error states.
7. Add tests:
   - toggle success/rollback
   - unauthorized behavior
   - grouped wishlist render

## 9) QA Scenarios

1. Logged-in user can add/remove package from wishlist.
2. Logged-in user can add/remove destination from wishlist.
3. Wishlist page reflects toggles immediately.
4. Refresh persists wishlist state.
5. Logged-out user sees auth prompt and no state corruption.
6. Invalid/removed items do not break page rendering.
