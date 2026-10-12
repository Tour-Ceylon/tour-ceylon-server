from app.config.database import SessionLocal
from app.services.admin.dashboard_service import AdminDashboardService
from app.models.user import User

db = SessionLocal()
s = AdminDashboardService(db)
user = User(id='usr_123', email='test@test.com', role='ADMIN')

try:
    res = s.get_snapshot(user)
    print('Snapshot keys:', res.keys())
    print('Listings keys:', res['listings'].keys())
    from app.schemas.admin.snapshot import AdminSnapshotResponse
    AdminSnapshotResponse(**res)
    print('Pydantic success')
except Exception as e:
    import traceback
    traceback.print_exc()
