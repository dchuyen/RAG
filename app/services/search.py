import logging
import os
from typing import Literal

import requests
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

logger = logging.getLogger(__name__)

_SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"


def search_web(
    q: str,
    max_results: int = 3,
    region: str = "vn-vi",
    safesearch: Literal["off", "moderate", "strict"] = "moderate",
) -> list[str]:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Search query must not be blank.")
    if not 1 <= max_results <= 100:
        raise HTTPException(status_code=422, detail="max_results must be between 1 and 100.")

    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="SERPAPI_API_KEY is not configured.",
        )

    if not region or region == "wt-wt":
        region = "vn-vi"
    region_parts = region.split("-", maxsplit=1)
    country = region_parts[0].lower()
    language = region_parts[1].lower() if len(region_parts) > 1 else "vi"

    try:
        response = requests.get(
            _SERPAPI_SEARCH_URL,
            params={
                "engine": "google",
                "q": query,
                "api_key": api_key,
                "gl": country,
                "hl": language,
                "safe": "off" if safesearch == "off" else "active",
                "num": max_results,
            },
            timeout=(5, 20),
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        logger.warning("SerpApi returned HTTP %s for query '%s'", status_code, query)
        raise HTTPException(
            status_code=502,
            detail=f"Dịch vụ tìm kiếm SerpApi trả về HTTP {status_code}.",
        ) from exc
    except requests.RequestException as exc:
        logger.warning(
            "SerpApi request failed for query '%s' (%s)",
            query,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Không thể kết nối tới dịch vụ tìm kiếm SerpApi.",
        ) from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="SerpApi trả về JSON không hợp lệ.",
        ) from exc

    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="SerpApi trả về dữ liệu không hợp lệ.")
    provider_error = result.get("error")
    if isinstance(provider_error, str) and provider_error:
        logger.warning("SerpApi search failed for query '%s': %s", query, provider_error)
        raise HTTPException(status_code=502, detail="SerpApi không thể hoàn tất tìm kiếm.")

    organic_results = result.get("organic_results", [])
    if not isinstance(organic_results, list):
        raise HTTPException(
            status_code=502,
            detail="SerpApi trả về danh sách kết quả không hợp lệ.",
        )

    links: list[str] = []
    seen: set[str] = set()
    for item in organic_results:
        if not isinstance(item, dict):
            continue
        link = item.get("link")
        if isinstance(link, str) and link.startswith(("http://", "https://")) and link not in seen:
            links.append(link)
            seen.add(link)
            if len(links) >= max_results:
                break

    return links
