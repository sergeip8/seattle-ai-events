"""Weekly Seattle AI events agent: discover -> fetch -> extract -> verify -> notify."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
import httpx

from discover import discover
from extract import extract
from fetch import USER_AGENT, fetch_page
from models import TZ, Event, Usage, normalize
from notify import format_digest, send_telegram
from verify import verify

ROOT = Path(__file__).resolve().parent.parent
SEEN_PATH = ROOT / "data" / "seen.json"
SEEN_RETENTION_DAYS = 60

DISCOVER_MODEL = os.getenv("DISCOVER_MODEL", "claude-sonnet-5-5")
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "claude-haiku-5-5")


def load_seen() -> dict:
    if SEEN_PATH.exists():
        return json.loads(SEEN_PATH.read_text() or "{}")
    return {}


def save_seen(seen: dict, now: datetime) -> None:
    cutoff = (now - timedelta(days=SEEN_RETENTION_DAYS)).isoformat()
    kept = {u: v for u, v in seen.items() if v.get("sent_at", "") >= cutoff}
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(kept, indent=2, ensure_ascii=False) + "\n")


def dedupe_events(events: list[Event]) -> list[Event]:
    """The same event is often listed on Luma and Meetup; keep the first."""
    out, keys = [], set()
    for e in sorted(events, key=lambda e: e.start):
        key = (normalize(e.title), e.start.astimezone(TZ).date())
        if key not in keys:
            keys.add(key)
            out.append(e)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print the digest instead of sending it")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--max-pages", type=int, default=25)
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 1
    tg_token, tg_chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not args.dry_run and not (tg_token and tg_chat):
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set (use --dry-run to test)", file=sys.stderr)
        return 1

    now = datetime.now(TZ)
    client = anthropic.Anthropic()
    usage = Usage()
    seen = load_seen()

    urls = discover(client, DISCOVER_MODEL, now, args.days, usage)
    print(f"Discovered {len(urls)} candidate URLs")

    accepted: list[Event] = []
    rejected: list[tuple[str, list[str]]] = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as http:
        for url in urls[: args.max_pages]:
            if url in seen:
                rejected.append((url, ["already_sent"]))
                continue
            text = fetch_page(url, http)
            if not text:
                rejected.append((url, ["fetch_failed"]))
                continue
            data = extract(client, EXTRACT_MODEL, url, text, now, usage)
            event, reasons = verify(data, url, text, now, args.days, set(seen))
            if event:
                accepted.append(event)
            else:
                rejected.append((url, reasons))

    events = dedupe_events(accepted)

    print("\nRejected:")
    for url, reasons in rejected:
        print(f"  {', '.join(reasons):40s} {url}")
    print(f"\n{usage.summary()}")

    digest = format_digest(events, checked=len(urls), rejected=len(rejected), usage=usage, days=args.days)
    if args.dry_run:
        print("\n" + digest)
        return 0

    send_telegram(tg_token, tg_chat, digest)
    for e in events:
        seen[e.url] = {"title": e.title, "start": e.start.isoformat(), "sent_at": now.isoformat()}
    save_seen(seen, now)
    print(f"Sent {len(events)} events to Telegram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
