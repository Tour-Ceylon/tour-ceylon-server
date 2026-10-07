from app.config.database import SessionLocal
from app.services.admin.dashboard_service import AdminDashboardService
from app.api.v1.admin.listings import create_tour_listing
from app.schemas.admin.listings import TourListingCreate
from app.models.user import User
import asyncio

db = SessionLocal()
s = AdminDashboardService(db)
payload = {'destinationId': '3fa85f64-5717-4562-b3fc-2c963f66afa6', 'title': 'Test Tour', 'description': 'desc', 'isActive': True, 'status': 'PUBLISHED', 'media': [], 'variants': [{'name': 'x', 'bookingUnit': 'per_person', 'capacityMin': 1, 'capacityMax': 6, 'isDefault': True, 'pricing': {'amount': 95, 'currency': 'USD', 'priority': 0}}], 'tourDetail': {'durationDays': 1, 'routeSummary': 'City Center', 'meetingPoint': 'City Center', 'itineraryHighlights': [], 'difficultyLevel': 'Easy', 'groupSizeMin': 1, 'groupSizeMax': 15, 'startTime': '09:00', 'endTime': '13:00', 'privateAvailable': False, 'pickupAvailable': False, 'dropoffAvailable': False, 'includedItems': [], 'excludedItems': [], 'languages': ['English'], 'whatToBring': [], 'childPolicy': '', 'pickupNotes': '', 'dropoffNotes': '', 'cancellationPolicy': '', 'accessibilityInfo': ''}}
tour_create = TourListingCreate(**payload)
user = User(id='usr_123', email='test@test.com', role='ADMIN')
try:
    res = s.create_listing('tour', tour_create.model_dump(by_alias=False), user)
    print('SUCCESS', res.keys())
except Exception as e:
    import traceback
    traceback.print_exc()
