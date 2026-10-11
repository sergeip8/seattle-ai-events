"""Shared types and helpers."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Los_Angeles")


@dataclass
class Event:
    title: str
    start: datetime
    location: str
    url: str
    evidence: str
    price: str = ""
    why: str = ""


class Usage:
    """Accumulates token and search usage across API calls."""

    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.searches = 0

    def add(self, u) -> None:
        self.calls += 1
        self.input_tokens += (
            (u.input_tokens or 0)
            + (getattr(u, "cache_read_input_tokens", 0) or 0)
            + (getattr(u, "cache_creation_input_tokens", 0) or 0)
        )
        self.output_tokens += u.output_tokens or 0
        stu = getattr(u, "server_tool_use", None)
        if stu is not None:
            self.searches += getattr(stu, "web_search_requests", 0) or 0

    def summary(self) -> str:
        return (
            f"API calls: {self.calls}, input tokens: {self.input_tokens:,}, "
            f"output tokens: {self.output_tokens:,}, web searches: {self.searches}"
        )


def normalize(s: str) -> str:
    """Lowercase, unify unicode punctuation and collapse whitespace."""
    s = unicodedata.normalize("NFKC", s or "").lower()
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                 ("–", "-"), ("—", "-"), (" ", " ")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()
