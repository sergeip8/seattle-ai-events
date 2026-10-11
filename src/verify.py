"""Step 3: deterministic checks. No LLM here: every rule is plain code against the page text.

The key check is that the model's `evidence` appears verbatim on the page we downloaded,
and that it contains the claimed date. This catches invented events and events stitched
together from details of two different pages.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from models import TZ, Event, normalize


def parse_start(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def date_in_evidence(start: datetime, evidence: str) -> bool:
    ev = normalize(evidence)
    local = start.astimezone(TZ)
    utc = start.astimezone(timezone.utc)
    # ISO dates (JSON-LD may store UTC, which can be the next calendar day)
    for d in (local, utc):
        if d.strftime("%Y-%m-%d") in ev:
            return True
    # US numeric, e.g. 10/13
    if re.search(rf"(?<!\d){local.month}/{local.day}(?!\d)", ev):
        return True
    # Month name + day number, e.g. "October 13" / "Oct 13" / "13 Oct"
    months = (local.strftime("%B").lower(), local.strftime("%b").lower())
    has_month = any(m in ev for m in months)
    has_day = re.search(rf"(?<!\d){local.day}(?!\d)", ev) is not None
    return has_month and has_day


def title_on_page(title: str, page_norm: str) -> bool:
    t = normalize(title)
    if not t:
        return False
    if t in page_norm:
        return True
    words = [w for w in re.findall(r"\w+", t) if len(w) > 2]
    if not words:
        return False
    found = sum(1 for w in words if w in page_norm)
    return found / len(words) >= 0.8


def verify(
    data: dict | None,
    url: str,
    page_text: str,
    now: datetime,
    days: int,
    seen_urls: set[str],
) -> tuple[Event | None, list[str]]:
    """Return (event, []) if all checks pass, otherwise (None, reasons)."""
    if not data:
        return None, ["no_extraction"]

    reasons: list[str] = []
    if not data.get("is_event_page"):
        return None, ["not_an_event_page"]
    if not data.get("is_technical_ai"):
        reasons.append("not_technical_ai")
    if data.get("is_in_person") is False:
        reasons.append("not_in_person")
    if url in seen_urls:
        reasons.append("already_sent")

    start = parse_start(data.get("start_iso", ""))
    if start is None:
        reasons.append("bad_date")
    elif not (now <= start <= now + timedelta(days=days)):
        reasons.append("outside_window")

    page_norm = normalize(page_text)
    evidence = data.get("evidence", "")
    if not evidence or normalize(evidence) not in page_norm:
        reasons.append("evidence_not_on_page")
    elif start is not None and not date_in_evidence(start, evidence):
        reasons.append("date_not_in_evidence")

    if not title_on_page(data.get("title", ""), page_norm):
        reasons.append("title_not_on_page")

    if reasons:
        return None, reasons

    return (
        Event(
            title=data["title"].strip(),
            start=start,
            location=data.get("location", "").strip(),
            url=url,
            evidence=evidence,
            price=(data.get("price") or "").strip(),
            why=(data.get("why") or "").strip(),
        ),
        [],
    )
