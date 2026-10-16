"""Seed the reference data the driver registration form depends on.

Production had empty luggage_size_types and vehicle_model_presets tables, so the form
fell back to built-in luggage sizes whose IDs did not exist, and driver sign-up failed with
a foreign key violation on driver_luggage_capacity.

The values below are the ones the admin portal's DriverRegistration form already ships with
(same luggage IDs, names and dimensions, same vehicle presets), so a form that is already open
keeps working. Safe to run more than once: existing rows are left untouched.

    python seed_driver_reference_data.py
"""
import json
import uuid
from urllib.parse import urlparse

from sqlalchemy import text

from app.config.database import engine

LUGGAGE_SIZE_TYPES = [
    ("11111111-1111-1111-1111-111111111101", "Small", "55 x 35 x 20 cm", "Cabin / Carry-on (up to 10kg)", 1),
    ("11111111-1111-1111-1111-111111111102", "Medium", "65 x 45 x 25 cm", "Medium suitcase (up to 20kg)", 2),
    ("11111111-1111-1111-1111-111111111103", "Large", "75 x 50 x 30 cm", "Large check-in suitcase (up to 30kg)", 3),
    ("11111111-1111-1111-1111-111111111104", "Extra Large", "85 x 60 x 35 cm", "Oversized / heavy luggage (30kg+)", 4),
]


def caps(small, medium, large, xl):
    return {"Small": small, "Medium": medium, "Large": large, "Extra Large": xl}


VEHICLE_PRESETS = [
    ("Toyota", "Prius", 4, caps(2, 2, 1, 0)),
    ("Toyota", "Axio", 4, caps(2, 2, 2, 0)),
    ("Toyota", "Allion", 4, caps(2, 2, 2, 0)),
    ("Toyota", "Premio", 4, caps(2, 2, 2, 0)),
    ("Toyota", "Aqua", 4, caps(2, 1, 0, 0)),
    ("Toyota", "Corolla Cross", 4, caps(3, 3, 2, 1)),
    ("Toyota", "KDH / HiAce (Standard Roof)", 9, caps(8, 6, 5, 3)),
    ("Toyota", "HiAce Commuter (High Roof)", 14, caps(10, 8, 6, 4)),
    ("Toyota", "Land Cruiser Prado", 6, caps(4, 4, 3, 2)),
    ("Suzuki", "Wagon R (FX / FZ / Stingray)", 4, caps(2, 1, 0, 0)),
    ("Suzuki", "Spacia / Custom", 4, caps(2, 1, 0, 0)),
    ("Suzuki", "Every (Van)", 4, caps(4, 3, 2, 1)),
    ("Suzuki", "Alto (800 / K10)", 4, caps(1, 1, 0, 0)),
    ("Honda", "Grace", 4, caps(2, 2, 2, 0)),
    ("Honda", "Vezel / HR-V", 4, caps(3, 2, 2, 0)),
    ("Honda", "Fit / Jazz", 4, caps(2, 2, 1, 0)),
    ("Nissan", "Caravan NV350", 9, caps(8, 6, 5, 3)),
    ("Nissan", "X-Trail", 5, caps(4, 3, 2, 1)),
    ("Mitsubishi", "Outlander PHEV", 5, caps(4, 3, 2, 1)),
    ("Hyundai", "Staria", 8, caps(6, 6, 4, 2)),
]

print(f"Target database host: {urlparse(str(engine.url)).hostname}")

with engine.begin() as conn:
    added_luggage = 0
    for lid, name, dims, desc, order in LUGGAGE_SIZE_TYPES:
        result = conn.execute(
            text(
                "INSERT INTO luggage_size_types (id, name, dimensions_display, description, sort_order, created_at, updated_at) "
                "VALUES (:id, :name, :dims, :desc, :order, now(), now()) ON CONFLICT DO NOTHING"
            ),
            {"id": lid, "name": name, "dims": dims, "desc": desc, "order": order},
        )
        added_luggage += result.rowcount

    added_presets = 0
    for make, model, seats, luggage in VEHICLE_PRESETS:
        exists = conn.execute(
            text("SELECT 1 FROM vehicle_model_presets WHERE make = :make AND model = :model"),
            {"make": make, "model": model},
        ).first()
        if exists:
            continue
        conn.execute(
            text(
                "INSERT INTO vehicle_model_presets (id, make, model, default_seats, default_luggage_capacity, is_active, created_at, updated_at) "
                "VALUES (:id, :make, :model, :seats, CAST(:luggage AS JSONB), true, now(), now())"
            ),
            {"id": str(uuid.uuid4()), "make": make, "model": model, "seats": seats, "luggage": json.dumps(luggage)},
        )
        added_presets += 1

    totals = (
        conn.execute(text("SELECT count(*) FROM luggage_size_types")).scalar(),
        conn.execute(text("SELECT count(*) FROM vehicle_model_presets")).scalar(),
    )

print(f"Added {added_luggage} luggage size types and {added_presets} vehicle presets.")
print(f"Tables now hold {totals[0]} luggage size types and {totals[1]} vehicle presets.")
