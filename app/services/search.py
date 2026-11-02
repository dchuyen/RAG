from typing import Literal

from ddgs import DDGS
from ddgs.exceptions import DDGSException
from fastapi import HTTPException


def search_web(
    q: str,
    max_results: int = 1,
    region: str = "wt-wt",
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
