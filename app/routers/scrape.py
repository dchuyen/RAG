import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlsplit

import requests
import trafilatura
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

_MAX_REDIRECTS = 5
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def _validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(
            status_code=422,
            detail="URL must use http or https and include a hostname.",
        )
    if parsed.username is not None or parsed.password is not None:
        raise HTTPException(
            status_code=422,
            detail="URLs containing credentials are not allowed.",
        )

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = {
            ipaddress.ip_address(address[4][0])
            for address in socket.getaddrinfo(
                parsed.hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="URL contains an invalid port.") from exc
    except OSError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not resolve the requested hostname.",
        ) from exc

    if not addresses or any(not address.is_global for address in addresses):
        raise HTTPException(
            status_code=422,
            detail="Only publicly reachable URLs can be scraped.",
        )


def _fetch_page(url: str) -> tuple[bytes, str]:
    current_url = url
    with requests.Session() as session:
        for redirect_count in range(_MAX_REDIRECTS + 1):
            _validate_public_url(current_url)
            try:
                response = session.get(
                    current_url,
                    allow_redirects=False,
                    stream=True,
                    timeout=(5, 20),
                    headers={"User-Agent": "RAGContentExtractor/1.0"},
                )
            except requests.RequestException as exc:
                raise HTTPException(
                    status_code=502,
                    detail="Could not fetch the requested webpage.",
                ) from exc

            with response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("Location")
                    if not location:
                        raise HTTPException(
                            status_code=502,
                            detail="The webpage returned a redirect without a destination.",
                        )
                    if redirect_count == _MAX_REDIRECTS:
                        raise HTTPException(
                            status_code=502,
                            detail="The webpage exceeded the redirect limit.",
                        )
                    current_url = urljoin(current_url, location)
                    continue

                try:
                    response.raise_for_status()
                except requests.HTTPError as exc:
                    status_code = (
                        404 if response.status_code == 404 else 502
                    )
                    raise HTTPException(
                        status_code=status_code,
                        detail=f"The webpage returned HTTP {response.status_code}.",
                    ) from exc

                content_type = response.headers.get("Content-Type", "").lower()
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    raise HTTPException(
                        status_code=415,
                        detail="The requested URL does not return an HTML page.",
                    )

                content = bytearray()
                try:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        content.extend(chunk)
                        if len(content) > _MAX_RESPONSE_BYTES:
                            raise HTTPException(
                                status_code=413,
                                detail="The webpage is larger than the 5 MB limit.",
                            )
                except requests.RequestException as exc:
                    raise HTTPException(
                        status_code=502,
                        detail="Could not read the requested webpage.",
                    ) from exc
                return bytes(content), current_url

    raise HTTPException(status_code=502, detail="Could not fetch the requested webpage.")


@router.get("/scrape")
def scrape_webpage(
    url: str = Query(min_length=1, max_length=2048, description="Public webpage URL"),
) -> dict[str, object]:
    html, final_url = _fetch_page(url)
    extracted = trafilatura.extract(
        html,
        url=final_url,
        output_format="json",
        with_metadata=True,
    )
    if not extracted:
        raise HTTPException(
            status_code=422,
            detail="Trafilatura could not extract content from the webpage.",
        )

    try:
        result = json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Trafilatura returned invalid extraction data.",
        ) from exc

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail="Trafilatura returned an unexpected result format.",
        )

    result = {
        key: result[key]
        for key in ("source", "date", "title")
        if key in result
    }

    plain_text = trafilatura.extract(
        html,
        url=final_url,
        output_format="txt",
        favor_precision=True,
    )
    if not plain_text:
        raise HTTPException(
            status_code=422,
            detail="Trafilatura could not extract plain text from the webpage.",
        )
    result["text"] = re.sub(
        r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)",
        "",
        plain_text,
    )
    return result
