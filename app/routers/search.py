from typing import Literal

from ddgs import DDGS
from ddgs.exceptions import DDGSException
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@router.get("/search")
def search_web(
    q: str = Query(min_length=1, max_length=500, description="Web search query"),
    max_results: int = Query(default=None, ge=1, le=50),
    region: str = Query(default="wt-wt"),
    safesearch: Literal["off", "moderate", "strict"] = "moderate",
) -> list[str]:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Search query must not be blank.")

    try:
        results = DDGS().text(
            query,
            region=region,
            safesearch="on" if safesearch == "strict" else safesearch,
            max_results=max_results,
        )
    except DDGSException as exc:
        if str(exc) == "No results found.":
            results = []
        else:
            raise HTTPException(
                status_code=502,
                detail="The web search provider could not complete the request.",
            ) from exc

    return [result["href"] for result in results if result.get("href")]
