from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_notifications(limit: int = 20, offset: int = 0):
    return {"notifications": [], "total": 0, "unread_count": 0}
