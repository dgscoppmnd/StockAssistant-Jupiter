import logging
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/web", tags=["web"])
logger = logging.getLogger("api.endpointWebs")


def search_web_duckduckgo(query: str, max_results: int = 5, timeout: int = 20) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    encoded_query = quote_plus(query.strip())
    url = f"https://duckduckgo.com/html/?q={encoded_query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("event=web_search_failed query=%s detail=%s", query, exc)
        raise HTTPException(status_code=502, detail="No fue posible consultar en la web") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, Any]] = []

    for item in soup.select(".result"):
        title_node = item.select_one(".result__a")
        snippet_node = item.select_one(".result__snippet")

        if not title_node:
            continue

        title = title_node.get_text(strip=True)
        link = title_node.get("href", "")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""

        rows.append(
            {
                "title": title,
                "url": link,
                "snippet": snippet,
                "source": "duckduckgo",
            }
        )

        if len(rows) >= max_results:
            break

    return rows


@router.get("/search")
def web_search(query: str = Query(..., min_length=2), max_results: int = Query(5, ge=1, le=10)):
    logger.info("event=web_search_start query=%s max_results=%s", query, max_results)
    results = search_web_duckduckgo(query=query, max_results=max_results)
    return {
        "query": query,
        "max_results": max_results,
        "results": results,
    }
