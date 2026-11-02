from fastapi import APIRouter

from app.services.health import get_health_status

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return get_health_status()
