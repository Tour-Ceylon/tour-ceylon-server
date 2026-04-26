# Activity → Experience/Safari Refactoring Plan

## Current-State Summary

The codebase has been **partially refactored** but has **critical import and logic errors**:

### Status ✓ (Already Done)
- **Models**: `ListingType` enum has `EXPERIENCE`, `SAFARI`, `TOUR`, `TRANSFER`, `HOTEL` (NO `ACTIVITY`)
- **Detail Models**: `ActivityDetail` model exists (serves `EXPERIENCE` listings)
- **Admin Routes**: Distinct endpoints exist:
  - `POST /admin/listings/stay` (HOTEL)
  - `POST /admin/listings/tour` (TOUR)
  - `POST /admin/listings/safari` (SAFARI)
  - `POST /admin/listings/experience` (EXPERIENCE with activity_detail)
  - `POST /admin/listings/transfer` (TRANSFER)
- **Admin Schemas**: Distinct create/response schemas for each type
- **Service Layer**: `AdminDashboardService` correctly maps:
  - "experience" → `ListingType.EXPERIENCE` + `activity_detail`
  - "safari" → `ListingType.SAFARI` + `safari_detail`

### Status ✗ (Broken / Needs Fixing)
1. **Import Errors**:
   - `app/schemas/admin/__init__.py` imports non-existent `ActivityListingCreate`, `ActivityListingResponse`
   - `app/schemas/admin/snapshot.py` imports non-existent `ActivityListingResponse`

2. **Snapshot Logic Error**:
   - `snapshot.py` expects `listings.activity` field but service creates `listings.experience`
   - Response model structure is incorrect

3. **Legacy Code** (unused, should be removed):
   - `app/api/v1/activities.py` - Old endpoint (not part of admin flow)
   - `app/repositories/activity_repo.py` - Old repository (not used by admin service)
   - `app/schemas/activity_schema.py` - Old schema (referenced by activities.py)

4. **Validation Issues**:
   - Main `listing_schema.py` has outdated validator for `EXPERIENCE` (maps to old "activity" concept)

### Existing Tests
- `app/tests/test_admin_listing_api.py` - Tests admin endpoints
- Tests should already cover experience/safari creation

---

## Files That Need Changes

### 1. **Fix Import Errors**
   - [ ] `app/schemas/admin/__init__.py` - Remove ActivityListing imports, add SafariListingCreate
   - [ ] `app/schemas/admin/snapshot.py` - Update imports, fix response model structure

### 2. **Fix Snapshot Logic**
   - [ ] `app/schemas/admin/snapshot.py` - Change `activity: list[...]` to `experience: list[...]`
   - [ ] `app/services/admin/dashboard_service.py` - Verify listing_groups structure (already correct)

### 3. **Clean Up Legacy Code**
   - [ ] `app/api/v1/activities.py` - Remove or deprecate
   - [ ] `app/repositories/activity_repo.py` - Remove
   - [ ] `app/schemas/activity_schema.py` - Remove

### 4. **Verify Main Schema**
   - [ ] `app/schemas/listing_schema.py` - Verify it correctly handles EXPERIENCE + activity_detail

### 5. **Update Tests** (if needed)
   - [ ] `app/tests/test_admin_listing_api.py` - Verify snapshot test includes "experience"

---

## Detailed Change Plan

### Phase 1: Fix Critical Errors

#### Change 1.1: Fix `app/schemas/admin/__init__.py`
**Current Issue**: Imports non-existent classes
**Fix**:
```python
# REMOVE these lines:
# ActivityListingCreate,
# ActivityListingResponse,

# ADD SafariListingCreate:
SafariListingCreate,
SafariListingResponse,
```

#### Change 1.2: Fix `app/schemas/admin/snapshot.py`
**Current Issue**:
- Imports non-existent `ActivityListingResponse`
- Response model has `activity` field but service creates `experience`

**Fix**:
```python
from app.schemas.admin.listings import (
    ExperienceListingResponse,  # Instead of ActivityListingResponse
    SafariListingResponse,
    StayListingResponse,
    TourListingResponse,
    TransferListingResponse,
)

class SnapshotListingsResponse(BaseModel):
    stay: list[StayListingResponse]
    tour: list[TourListingResponse]
    experience: list[ExperienceListingResponse]  # Changed from "activity"
    safari: list[SafariListingResponse]
    transfer: list[TransferListingResponse]
```

### Phase 2: Clean Up Legacy Code

#### Change 2.1: Remove Old Activity Files
- Delete: `app/api/v1/activities.py` (old endpoint, not part of admin flow)
- Delete: `app/repositories/activity_repo.py` (outdated, not used)
- Delete: `app/schemas/activity_schema.py` (old schema, only referenced by deleted files)

**Rationale**: These are remnants of the old API. The new admin flow uses:
- `/admin/listings/experience` endpoint
- `AdminDashboardService` service layer
- `adminActivityDetail` schema

### Phase 3: Verify Core Logic

#### Change 3.1: Verify `app/services/admin/dashboard_service.py`
**Status**: Already correct ✓
- `VALID_LISTING_CATEGORIES = {"stay", "tour", "safari", "experience", "transfer"}` ✓
- `LISTING_TYPE_MAP["experience"] = ListingType.EXPERIENCE` ✓
- `_detail_key_for_category("experience") = "activity_detail"` ✓

**Action**: No changes needed, just verify it's working as intended.

#### Change 3.2: Verify `app/models/enum.py`
**Status**: Already correct ✓
- `ListingType` enum has `EXPERIENCE`, `SAFARI` (no `ACTIVITY`)

**Action**: No changes needed.

---

## Validation Requirements

### ✓ After Changes All of These Must Work:

1. **Experience Listing Creation**:
   ```
   POST /admin/listings/experience
   {
     "destinationId": "...",
     "title": "...",
     "activityDetail": {
       "activityType": "...",
       "durationMinutes": 120,
       ...
     },
     "variants": [...]
   }
   → Response includes category: "experience"
   ```

2. **Safari Listing Creation**:
   ```
   POST /admin/listings/safari
   {
     "destinationId": "...",
     "title": "...",
     "safariDetail": {
       "nationalPark": "...",
       "safariType": "morning",
       ...
     },
     "variants": [...]
   }
   → Response includes category: "safari"
   ```

3. **Snapshot Response**:
   ```
   GET /admin/snapshot
   → Returns {
       "listings": {
         "stay": [...],
         "tour": [...],
         "experience": [...],    # NOT "activity"
         "safari": [...],
         "transfer": [...]
       },
       ...
     }
   ```

4. **No Import Errors**:
   - Python imports work cleanly
   - `from app.schemas.admin import ActivityListing...` → FAILS (expected)
   - `from app.schemas.admin import ExperienceListingCreate` → SUCCESS

5. **No Unused Files**:
   - `activity_repo.py` not imported anywhere
   - `activities.py` endpoint not registered in main app (or explicitly deprecated)

---

## Test Plan

### Existing Tests to Verify:
- [ ] `test_admin_stay_listing_create_returns_camel_case_fields` - must pass
- [ ] Check for tests that create experience listings - should pass
- [ ] Check for tests that create safari listings - should pass

### New Tests to Add (if missing):
- [ ] Test snapshot includes "experience" (not "activity")
- [ ] Test snapshot includes "safari"
- [ ] Test experience listing requires activity_detail
- [ ] Test safari listing requires safari_detail

---

## Breaking Changes & Rollout Risks

### Breaking Changes:
1. **API Response Format**: Snapshot now has `experience` instead of `activity`
   - Clients consuming `listings.activity` will break
   - Clients consuming `listings.experience` will now work

2. **Removed Endpoints** (if `/api/v1/activities` was public):
   - Old `POST /activities` endpoint no longer exists
   - Only `/admin/listings/experience` endpoint valid

### Migration Strategy for Clients:
1. Update API clients to expect `listings.experience` in snapshot response
2. Update any dashboards that show "activity" listings to show "experience"
3. No database migration needed (no old "activity" records exist)

### Backward Compatibility:
- No explicit compatibility layer provided
- This is a breaking change to admin API response schema
- Recommend versioning the API if needed

---

## Summary of Changes

| File | Change Type | Details |
|------|------------|---------|
| `app/schemas/admin/__init__.py` | Fix | Remove ActivityListing imports |
| `app/schemas/admin/snapshot.py` | Fix | Import ExperienceListingResponse, change field name |
| `app/api/v1/activities.py` | Delete | Remove old endpoint |
| `app/repositories/activity_repo.py` | Delete | Remove unused repository |
| `app/schemas/activity_schema.py` | Delete | Remove unused schema |
| Tests | Update | Verify snapshot includes "experience" |

**Total files to modify**: 5
**Total files to delete**: 3
**Estimated blast radius**: Low (errors are isolated to admin snapshot response)
