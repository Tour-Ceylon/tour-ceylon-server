"""Create the tables used by the driver portal features, if they do not exist yet:

  driver_profile_change_requests   profile details a driver sent for admin approval
  driver_avatar_submissions        profile photos waiting for (or given) admin approval
  transport_booking_driver_notes   notes an admin writes for the driver assigned to a booking

Tables are no longer created automatically at startup, so run this once per database. It only creates missing
tables; it never alters or deletes existing data, and it is safe to run again.

    python create_driver_portal_tables.py
"""
from urllib.parse import urlparse

from sqlalchemy import inspect

from app.config.database import engine
from app.models.driver import DriverAvatarSubmission, DriverProfileChangeRequest, TransportBookingDriverNote

print(f"Target database host: {urlparse(str(engine.url)).hostname}")

for model in (DriverProfileChangeRequest, DriverAvatarSubmission, TransportBookingDriverNote):
    table = model.__table__
    if inspect(engine).has_table(table.name):
        print(f"  exists   {table.name}")
    else:
        table.create(bind=engine)
        print(f"  created  {table.name}")
