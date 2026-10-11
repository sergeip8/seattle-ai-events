"""Step 2: turn one fetched page into one structured event, with verbatim evidence."""
from __future__ import annotations

from datetime import datetime

import anthropic

from models import Usage

RECORD_TOOL = {
    "name": "record_event",
    "description": "Record the single event this page is about.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_event_page": {
                "type": "boolean",
                "description": "True only if the page is about exactly one specific event. False for listings, calendars, articles about many events, or non-event pages.",
            },
            "title": {"type": "string", "description": "Event title exactly as written on the page."},
            "start_iso": {
                "type": "string",
                "description": "Start date and time in ISO 8601, e.g. 2026-10-13T17:30:00-07:00. Use Seattle local time if the page gives local time.",
            },
            "location": {"type": "string", "description": "Venue name and/or address as written on the page."},
            "price": {"type": "string", "description": "Price as written, or empty if not stated."},
            "is_technical_ai": {
                "type": "boolean",
                "description": "True for technical AI/ML events (talks, demos, builder meetups, hackathons). False for sales/GTM, generic networking, webinars.",
            },
            "is_in_person": {"type": "boolean"},
            "evidence": {
                "type": "string",
                "description": "A snippet copied character-for-character from the page (max ~300 chars) that contains the event date. May be the startDate line from the JSON-LD.",
            },
            "why": {
                "type": "string",
                "description": "One short line in Russian on why a senior engineer moving into AI might attend.",
            },
        },
        "required": ["is_event_page", "title", "start_iso", "location", "is_technical_ai", "is_in_person", "evidence"],
    },
}

SYSTEM = """You extract event details from a single web page.
Rules:
- Use ONLY the page content provided. Never use outside knowledge, never guess.
- The page must be about exactly one event; otherwise set is_event_page=false and fill other fields with empty values.
- `evidence` must be copied exactly from the page text, not paraphrased, and must contain the date.
- Today is {today}. If the page omits the year, infer the next upcoming occurrence."""


def extract(
    client: anthropic.Anthropic,
    model: str,
    url: str,
    page_text: str,
    now: datetime,
    usage: Usage,
) -> dict | None:
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM.format(today=now.strftime("%Y-%m-%d")),
        tools=[RECORD_TOOL],
        tool_choice={"type": "tool", "name": "record_event"},
        messages=[{"role": "user", "content": f"URL: {url}\n\n<page>\n{page_text}\n</page>"}],
    )
    usage.add(resp.usage)
    for block in resp.content:
        if block.type == "tool_use":
            return dict(block.input)
    return None
