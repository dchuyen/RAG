from typing import Literal

from fastapi import APIRouter, Query

from app.services.search import search_web as run_search_web

router = APIRouter()


@router.get("/search")
def search_web(
    q: str = Query(min_length=1, max_length=500, description="Web search query"),
    max_results: int = Query(default=1, ge=1, le=50),
    region: str = Query(default="wt-wt"),
    safesearch: Literal["off", "moderate", "strict"] = "moderate",
) -> list[str]:
    return run_search_web(q, max_results, region, safesearch)
