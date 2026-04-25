"""
Fetch a URL and extract the main body text.
Uses requests + BeautifulSoup. No browser automation in v1.
"""
from __future__ import annotations

import logging
import re
import requests
from bs4 import BeautifulSoup
from config import FETCH_TIMEOUT, MAX_TEXT_CHARS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Tags whose content we always strip (scripts, ads, nav, etc.)
STRIP_TAGS = {
    "script", "style", "noscript", "nav", "footer", "header",
    "aside", "form", "button", "iframe", "svg", "figure",
}


def fetch_and_extract(url: str) -> dict:
    """
    Returns:
        {
            "url": str,
            "title": str,
            "text": str,          # up to MAX_TEXT_CHARS
            "ok": bool,
            "error": str | None,
        }
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Fetch failed for %s: %s", url, exc)
        return {"url": url, "title": "", "text": "", "ok": False, "error": str(exc)}

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        msg = f"Non-HTML content type: {content_type}"
        logger.warning("Skipping %s — %s", url, msg)
        return {"url": url, "title": "", "text": "", "ok": False, "error": msg}

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        for tag in soup(STRIP_TAGS):
            tag.decompose()

        # Prefer article / main content blocks
        content_block = (
            soup.find("article")
            or soup.find("main")
            or soup.find(id=re.compile(r"content|main|article", re.I))
            or soup.find(class_=re.compile(r"content|main|article|post|entry", re.I))
            or soup.body
        )

        if content_block:
            raw = content_block.get_text(separator="\n")
        else:
            raw = soup.get_text(separator="\n")

        # Collapse blank lines and trim each line
        lines = [line.strip() for line in raw.splitlines()]
        lines = [l for l in lines if l]
        cleaned = "\n".join(lines)

        text = cleaned[:MAX_TEXT_CHARS]
        return {"url": url, "title": title, "text": text, "ok": True, "error": None}

    except Exception as exc:
        logger.warning("Extraction failed for %s: %s", url, exc)
        return {"url": url, "title": "", "text": "", "ok": False, "error": str(exc)}
