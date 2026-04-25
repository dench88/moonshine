"""
Search abstraction layer.
Swap SEARCH_PROVIDER in config.py to plug in a real provider.

Each provider must return a list of dicts:
    [{"url": str, "title": str, "snippet": str}, ...]
"""
from __future__ import annotations

import logging
import requests
from config import SEARCH_PROVIDER, SEARXNG_URL, BRAVE_API_KEY

logger = logging.getLogger(__name__)


def search(query: str, num_results: int = 5) -> list[dict]:
    """Dispatch to the configured provider."""
    providers = {
        "mock": _mock_search,
        "searxng": _searxng_search,
        "brave": _brave_search,
    }
    fn = providers.get(SEARCH_PROVIDER)
    if fn is None:
        raise ValueError(f"Unknown SEARCH_PROVIDER: {SEARCH_PROVIDER!r}")
    logger.info("Search [%s]: %s", SEARCH_PROVIDER, query)
    return fn(query, num_results)


# ---------------------------------------------------------------------------
# Mock — returns empty results so the loop can run without a real search API
# ---------------------------------------------------------------------------

def _mock_search(query: str, num_results: int) -> list[dict]:
    logger.warning("Mock search in use — returning empty results for: %s", query)
    return []


# ---------------------------------------------------------------------------
# SearXNG
# ---------------------------------------------------------------------------

def _searxng_search(query: str, num_results: int) -> list[dict]:
    params = {
        "q": query,
        "format": "json",
        "engines": "google,bing,duckduckgo",
        "language": "en",
    }
    try:
        resp = requests.get(
            f"{SEARXNG_URL}/search",
            params=params,
            timeout=15,
            headers={"User-Agent": "moonshine-research/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in data.get("results", [])[:num_results]:
            results.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "snippet": r.get("content", ""),
            })
        return results
    except Exception as exc:
        logger.error("SearXNG search failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Brave Search API
# ---------------------------------------------------------------------------

def _brave_search(query: str, num_results: int) -> list[dict]:
    if not BRAVE_API_KEY:
        logger.error("BRAVE_API_KEY not set")
        return []
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {"q": query, "count": num_results, "text_decorations": False}
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in data.get("web", {}).get("results", [])[:num_results]:
            results.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "snippet": r.get("description", ""),
            })
        return results
    except Exception as exc:
        logger.error("Brave search failed: %s", exc)
        return []
