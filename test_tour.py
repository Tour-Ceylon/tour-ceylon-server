from app.schemas.admin.listings import TourListingCreate
from pydantic import ValidationError
payload = {'destinationId': '3fa85f64-5717-4562-b3fc-2c963f66afa6', 'title': 'Test Tour', 'description': 'desc', 'isActive': True, 'status': 'PUBLISHED', 'media': [], 'variants': [{'name': 'x', 'bookingUnit': 'per_person', 'capacityMin': 1, 'capacityMax': 6, 'isDefault': True, 'pricing': {'amount': 95, 'currency': 'USD', 'priority': 0}}], 'tourDetail': {'durationDays': 1, 'routeSummary': 'City Center', 'meetingPoint': 'City Center', 'itineraryHighlights': [], 'difficultyLevel': 'Easy', 'groupSizeMin': 1, 'groupSizeMax': 15, 'startTime': '09:00', 'endTime': '13:00', 'privateAvailable': False, 'pickupAvailable': False, 'dropoffAvailable': False, 'includedItems': [], 'excludedItems': [], 'languages': ['English'], 'whatToBring': [], 'childPolicy': '', 'pickupNotes': '', 'dropoffNotes': '', 'cancellationPolicy': '', 'accessibilityInfo': ''}}
try:
  obj = TourListingCreate(**payload)
  print('Pydantic success')
except ValidationError as e:
  print('Pydantic Error:', e)
