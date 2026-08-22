import os
from dotenv import load_dotenv
load_dotenv()
from app.config.database import SessionLocal
from app.services.admin.dashboard_service import AdminDashboardService
from uuid import UUID

db = SessionLocal()
service = AdminDashboardService(db)
import traceback
try:
    service.update_listing_status('stay', UUID('612c1048-b724-4339-a72f-66b9f7313520'), 'PUBLISHED')
except Exception as e:
    traceback.print_exc()
