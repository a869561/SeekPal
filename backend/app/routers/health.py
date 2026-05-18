from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.database import is_connected

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "success": True,
        "status": "up",
        "db": "up" if is_connected() else "down",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
