# Dependency Map: Activity/Experience/Safari References

## Files Referencing "Activity" Concept

### Direct References (40+ occurrences)

```
app/models/activityDetail.py
├─ defines ActivityDetail model
├─ has relationship back to Listing
└─ used by Listing.activity_detail

app/models/listing.py
├─ imports ActivityDetail
├─ has relationship: activity_detail = relationship("ActivityDetail", ...)
└─ used by all listing creation/retrieval

app/schemas/listing_schema.py
├─ imports ListingType enum
├─ ActivityDetailBase, ActivityDetailUpdate, ActivityDetailResponse schemas
├─ ListingBase validator: ListingType.EXPERIENCE → activity_detail (required)
└─ ListingResponse includes activity_detail field

app/schemas/admin/listings.py
├─ AdminActivityDetail schema
├─ ExperienceListingCreate: requires activity_detail
├─ ExperienceListingResponse: includes activity_detail
├─ ListingUpdateRequest: includes activity_detail field
└─ Used by admin API routes

app/schemas/admin/__init__.py [BROKEN]
├─ imports ActivityListingCreate (does NOT exist)
├─ imports ActivityListingResponse (does NOT exist)
└─ Should import ExperienceListingCreate, ExperienceListingResponse instead

app/schemas/admin/snapshot.py [BROKEN]
├─ imports ActivityListingResponse (does NOT exist)
├─ Response model has field: activity: list[ActivityListingResponse]
├─ Should have: experience: list[ExperienceListingResponse]
└─ Used by snapshot endpoint

app/services/admin/dashboard_service.py
├─ _detail_key_for_category("experience") = "activity_detail"
├─ _normalize_detail_payload(detail_key="activity_detail", ...)
├─ _build_activity_detail(listing) helper method
└─ get_snapshot() returns listing_groups["experience"] = [...] ✓ CORRECT

app/api/v1/admin/listings.py
├─ /experience endpoint uses AdminActivityDetail
├─ schema handling for experience listings
└─ Correctly calls service.create_listing("experience", ...)

app/api/v1/activities.py [LEGACY - UNUSED]
├─ Old endpoint POST /activities
├─ Uses ActivityRepository (also unused)
├─ Creates ActivityDetail directly (not integrated with Listing)
└─ Should be REMOVED

app/repositories/activity_repo.py [LEGACY - UNUSED]
├─ ActivityRepository class
├─ Only referenced by old activities.py endpoint
├─ Not used by AdminDashboardService
└─ Should be REMOVED

app/repositories/admin/listing_repo.py
├─ _base_query() joins activity_detail relationship
├─ Used by AdminDashboardService
└─ (already correct, no changes needed)

app/tests/test_admin_listing_api.py
├─ Test files may reference creating experience/safari listings
└─ Snapshot tests should verify "experience" field (not "activity")
```

## Dependency Graph

```
┌─────────────────────────────────┐
│ Admin Routes                    │
│ /listings/stay                  │
│ /listings/tour                  │
│ /listings/safari                │
│ /listings/experience ◄─┐        │
│ /listings/transfer              │
└───────────┬─────────────┼───────┘
            │             │
            ▼             │
┌─────────────────────────┼──────────┐
│ AdminDashboardService   │          │
│ .create_listing()       │          │
│ .update_listing()       │          │
└──────────┬──────────────┼──────────┘
           │              │
           ▼              ▼
┌────────────────────────────────┐
│ Schemas (admin/listings.py)    │
│ ExperienceListingCreate ◄──────┼─── Uses activity_detail: AdminActivityDetail
│ ExperienceListingResponse      │
└────────────────────────────────┘
           │
           ▼
┌────────────────────────────────┐
│ ListingRepository              │
│ .create()                      │
│ .update()                      │
└───────────┬────────────────────┘
            │
            ▼
┌────────────────────────────────┐
│ Models                         │
│ Listing ─► activity_detail ◄───┼─── ActivityDetail model
│          ─► safari_detail      │
│          ─► variants           │
│          ─► ...                │
└────────────────────────────────┘

BROKEN CHAIN:
┌────────────────────────────────┐
│ Snapshot Response              │
│ (admin/snapshot.py) [BROKEN]   │
│ expects: activity: [...]  [X]  │
├────────────────────────────────┤
│ imports:                       │
│ ActivityListingResponse [X]    │
│ (does not exist)               │
└────────────────────────────────┘
```

## Import Chain Issues

### Chain 1: Snapshot Import Error [CRITICAL]
```
app/schemas/admin/snapshot.py
  ├─ imports ActivityListingResponse  ← DOES NOT EXIST
  └─ SnapshotListingsResponse.activity field  ← WRONG (should be "experience")

app/schemas/admin/__init__.py
  ├─ imports ActivityListingCreate    ← DOES NOT EXIST
  ├─ imports ActivityListingResponse  ← DOES NOT EXIST
  └─ exports to app.schemas.admin package
```

### Chain 2: Service Response Building [CORRECT]
```
AdminDashboardService.get_snapshot()
  ├─ lists listing_groups["experience"]  ✓
  ├─ lists listing_groups["safari"]      ✓
  ├─ lists listing_groups["tour"]        ✓
  └─ builds responses via _build_listing_response()

_build_listing_response(listing: Listing)
  ├─ category = CATEGORY_BY_LISTING_TYPE[listing.listing_type]
  ├─ if listing_type == EXPERIENCE → category = "experience"  ✓
  ├─ if listing_type == SAFARI → category = "safari"  ✓
  └─ includes activity_detail if exists  ✓
```

## What Needs to Change

### Must Fix (Breaking Imports):
1. Remove non-existent imports from `__init__.py`
2. Fix snapshot response model structure
3. Delete legacy unused files

### Should Verify (Already Correct):
- Service layer already creates experience/safari correctly
- Admin routes already separate experience/safari
- Models already use ActivityDetail for experience

### No Changes Needed To:
- Models (enum, listing, activityDetail)
- Service layer logic
- Admin routes
- Main schema validators
