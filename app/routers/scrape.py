from fastapi import APIRouter, Query

from app.services.scrape import scrape_webpage as run_scrape_webpage

router = APIRouter()


@router.get("/scrape")
def scrape_webpage(
    url: str = Query(min_length=1, max_length=2048, description="Public webpage URL"),
) -> dict[str, object]:
    return run_scrape_webpage(url)
