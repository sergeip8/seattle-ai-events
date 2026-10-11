"""Download an event page and reduce it to text the model (and the verifier) can use."""
from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (compatible; seattle-ai-events/0.1; "
    "+https://github.com/sergeip8/seattle-ai-events)"
)
MAX_CHARS = 30_000  # keeps extraction cheap; evidence is checked against this same text


def fetch_page(url: str, client: httpx.Client) -> str | None:
    try:
        r = client.get(url, follow_redirects=True, timeout=20)
    except httpx.HTTPError:
        return None
    if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
        return None
    return html_to_text(r.text)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Capture these before stripping scripts: JSON-LD often holds the event's
    # name/startDate/location even on pages that render the rest with JavaScript.
    title = soup.title.get_text(strip=True) if soup.title else ""
    json_ld = [
        s.get_text(strip=True)
        for s in soup.find_all("script", type="application/ld+json")
        if s.get_text(strip=True)
    ]

    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "form"]):
        tag.decompose()

    text = soup.get_text("\n")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()

    parts = []
    if title:
        parts.append(f"PAGE TITLE: {title}")
    if json_ld:
        parts.append("STRUCTURED DATA (JSON-LD):\n" + "\n".join(json_ld))
    parts.append("PAGE TEXT:\n" + text)
    return "\n\n".join(parts)[:MAX_CHARS]
