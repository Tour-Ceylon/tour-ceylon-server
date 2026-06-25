# Phase 3 Stay Inventory And Availability

## Overview
This document summarizes the Phase 3 hotel inventory and availability feature implemented in the backend for Tour Ceylon.

The feature introduces a hotel-only inventory subsystem that runs alongside the existing generic `listing_variants` availability flow. It does not replace the old `availability_calendar` used by tours, activities, safaris, transfers, and other non-stay products.

## Core Goal
Hotels now support real room-level inventory.

Example:
- Oceanview Hotel can have 5 Deluxe rooms, 10 Triple rooms, 10 Double rooms, and 5 Single rooms.
- Each physical room is stored in `stay_room_units`.
- Example room numbers:
  - `TR001`, `TR002`
  - `DR001`, `DR002`
  - `SR001`

Availability is calculated per night using `[check_in, check_out)`.

Example:
- Booking `2026-06-23` to `2026-06-28`
- Blocks nights: `2026-06-23`, `2026-06-24`, `2026-06-25`, `2026-06-26`, `2026-06-27`
- Rooms become available again on `2026-06-28`

## New Stay Inventory Data Model
The following stay-specific tables were added:

- `stay_bookings`
  - Stay-specific booking header linked to the existing parent `bookings` table.
  - Stores property, guest contact details, stay dates, and stay booking status.

- `stay_booking_rooms`
  - Stores exact assigned `room_unit_id` values.
  - Stores `room_type_id`, `check_in_date`, `check_out_date`, nightly rate, and guest count.

- `stay_room_blocks`
  - Supports manual closures and maintenance blocks.
  - Stores block date range, reason, block type, and actor.

- `stay_room_type_calendar`
  - Stores cached daily totals per property and room type.
  - Includes:
    - `total_units`
    - `booked_units`
    - `blocked_units`
    - `available_units`

## Existing Stay Tables Used
This feature builds on the existing stay domain:

- `stay_properties`
- `stay_room_types`
- `stay_room_units`

Important existing constraint retained:
- `UNIQUE(property_id, room_number)` on `stay_room_units`

## Booking And Availability Rules
### Overlap rule
A room is unavailable if:

`existing_check_in < requested_check_out AND existing_check_out > requested_check_in`

### Room assignment flow
When a customer books `N` rooms of a room type:
- The system finds matching `stay_room_units`
- Excludes rooms already booked for overlapping nights
- Excludes blocked rooms for overlapping nights
- Selects exact available units
- Freezes them in `stay_booking_rooms`

### Oversell prevention
The stay inventory service validates:
- date range correctness
- room type belongs to the selected property
- guest count does not exceed room type capacity
- enough units remain available for every night in the range

### Cached calendar refresh
The room-type calendar is recalculated after:
- room block create/release
- stay booking create
- other stay inventory operations that affect room totals or occupancy

## Public Stay API
### Search availability
Route:

`POST /api/v1/stays/availability`

Request supports:
- `propertyId`
- `checkInDate`
- `checkOutDate`
- `guests`
- optional `roomTypeId`

Response includes:
- available room types
- available count
- nightly prices
- total price
- cancellation info
- max guests

### Create stay booking
Route:

`POST /api/v1/stays/bookings`

Request supports:
- `userId`
- `propertyId`
- `checkInDate`
- `checkOutDate`
- `guestName`
- `guestEmail`
- `guestPhone`
- `specialRequests`
- `items[]`

Each booking item supports:
- `roomTypeId`
- `roomCount`
- `guests`
- optional traveler payload data

Behavior:
- creates parent `bookings` record
- creates `stay_bookings`
- assigns exact room units
- creates `stay_booking_rooms`
- refreshes `stay_room_type_calendar`

## Vendor Stay API
Base path:

`/api/v1/vendor/stays`

Implemented capabilities:
- update stay property
- view property inventory
- create/update/delete room types
- create/update/delete room units
- view availability calendar
- block rooms
- release blocks
- view stay bookings for owned properties

Vendor safety:
- vendors can only access their own stay properties
- a vendor cannot backfill or manage another vendor’s hotel listing

## Admin Stay API
Base path:

`/api/v1/admin/stays`

Implemented capabilities:
- view inventory for any property
- create/update/delete room types
- create/update/delete room units
- view room-type calendar
- block and unblock rooms
- list stay bookings
- create admin-confirmed stay bookings

## Service Layer
Main backend logic lives in:

[`app/services/stay_inventory_service.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/services/stay_inventory_service.py)

Responsibilities:
- property inventory retrieval
- room type CRUD
- room unit CRUD
- room block creation and release
- room availability search
- exact room allocation
- stay booking creation
- daily room-type calendar refresh

## Files Added Or Updated
### Added
- [`alembic/versions/20260623_add_stay_inventory.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/alembic/versions/20260623_add_stay_inventory.py)
- [`app/api/v1/stays.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/api/v1/stays.py)
- [`app/api/v1/admin/stays.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/api/v1/admin/stays.py)
- [`app/services/stay_inventory_service.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/services/stay_inventory_service.py)
- [`app/tests/conftest.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/tests/conftest.py)
- [`app/tests/test_stay_inventory.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/tests/test_stay_inventory.py)

### Updated
- [`app/api/router.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/api/router.py)
- [`app/api/v1/admin/router.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/api/v1/admin/router.py)
- [`app/api/v1/vendor_stays.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/api/v1/vendor_stays.py)
- [`app/models/__init__.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/models/__init__.py)
- [`app/models/booking.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/models/booking.py)
- [`app/models/enum.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/models/enum.py)
- [`app/models/stay.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/models/stay.py)
- [`app/repositories/stay_repo.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/repositories/stay_repo.py)
- [`app/schemas/stay_schema.py`](/Users/umesh.pathirana/Documents/Personal/Travel_Ready_Tours/tour-ceylon-server/app/schemas/stay_schema.py)

## Tests Implemented
Stay-specific tests were added for:
- nightly availability behavior
- exact room allocation
- blocked-room exclusion
- vendor ownership restrictions
- public stay booking route behavior

Scenario covered:
- Oceanview Triple rooms `TR001` to `TR010`
- Booking A:
  - `2026-06-23` to `2026-06-28`
  - 2 rooms
  - assigned `TR001`, `TR002`
- Booking B:
  - `2026-06-24` to `2026-06-30`
  - 8 rooms
  - assigned `TR003` to `TR010`

Expected availability:
- `2026-06-23`: 8 available
- `2026-06-24` to `2026-06-27`: 0 available
- `2026-06-28` to `2026-06-29`: 2 available

## How To Run
### Apply migrations
```bash
alembic upgrade head
```

### Run stay inventory tests
```bash
PYTHONPATH=. python -m pytest app/tests/test_stay_inventory.py -q
```

## Notes
- Existing generic availability remains separate and unchanged in design.
- The backend stay feature is implemented.
- Admin/vendor portal UI integration was not added in this backend workspace step.
