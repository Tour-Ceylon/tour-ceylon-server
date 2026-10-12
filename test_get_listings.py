from app.config.database import SessionLocal
from app.services.admin.dashboard_service import AdminDashboardService
from app.models.user import User
from app.schemas.admin.listings import TourListingResponse

db = SessionLocal()
s = AdminDashboardService(db)
user = User(id='usr_123', email='test@test.com', role='ADMIN')
try:
    res = s.get_listings('tour', user)
    print(res)
    [TourListingResponse(**r) for r in res]
    print('Pydantic success')
except Exception as e:
    import traceback
    traceback.print_exc()
