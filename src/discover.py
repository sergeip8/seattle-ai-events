"""Step 1: use Claude + server-side web search to find candidate event pages.

The model only returns URLs here. It never describes events at this stage, so it
has nothing to hallucinate that later steps would trust.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import anthropic

from models import Usage

SUBMIT_TOOL = {
    "name": "submit_candidates",
    "description": "Submit the final list of URLs of individual event pages.",
    "input_schema": {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "One URL per event. Individual event pages only, not listing/calendar pages.",
            }
        },
        "required": ["urls"],
    },
}

PROMPT = """Find in-person technical AI events in the Seattle area (Seattle, Bellevue, Redmond, \
Kirkland, Bothell, Woodinville) between {start} and {end}.

Good sources: geekwire.com/calendar, seattle.aitinkerers.org, lu.ma / luma.com Seattle events, \
meetup.com AI/ML groups in Seattle, WTIA events.

Include: AI/ML meetups, builder sessions, demo nights, technical talks, hackathons, paper reading groups.
Exclude: sales/GTM/marketing events, pure networking mixers, online-only webinars, vendor pitches.

Search as needed, then call submit_candidates with the URL of each individual event page \
(at most {max_urls}). Prefer the organizer's own page (e.g. the Luma or Meetup page) over a \
news article about the event."""


def discover(
    client: anthropic.Anthropic,
    model: str,
    now: datetime,
    days: int,
    usage: Usage,
    max_urls: int = 25,
    max_searches: int = 8,
) -> list[str]:
    tools = [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_searches,
            "user_location": {
                "type": "approximate",
                "city": "Seattle",
                "region": "Washington",
                "country": "US",
                "timezone": "America/Los_Angeles",
            },
        },
        SUBMIT_TOOL,
    ]
    prompt = PROMPT.format(
        start=now.strftime("%Y-%m-%d"),
        end=(now + timedelta(days=days)).strftime("%Y-%m-%d"),
        max_urls=max_urls,
    )
    messages: list[dict] = [{"role": "user", "content": prompt}]

    for _ in range(6):
        resp = client.messages.create(
            model=model, max_tokens=4096, tools=tools, messages=messages
        )
        usage.add(resp.usage)

        for block in resp.content:
            if block.type == "tool_use" and block.name == "submit_candidates":
                return _dedupe(block.input.get("urls", []))[:max_urls]

        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "pause_turn":
            # The model finished without submitting; ask once more explicitly.
            messages.append(
                {"role": "user", "content": "Now call submit_candidates with the event page URLs you found."}
            )
    return []


def _dedupe(urls: list[str]) -> list[str]:
    seen, out = set(), []
    for u in urls:
        key = u.strip().rstrip("/").split("#")[0]
        if key.startswith("http") and key not in seen:
            seen.add(key)
            out.append(u.strip())
    return out
