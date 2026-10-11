"""Step 4: format the digest and send it to Telegram."""
from __future__ import annotations

from html import escape

import httpx

from models import TZ, Event, Usage

WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
TELEGRAM_LIMIT = 4000  # API limit is 4096; leave room


def format_digest(events: list[Event], checked: int, rejected: int, usage: Usage, days: int) -> str:
    lines = [f"<b>AI-события в Сиэтле на {days} дней</b>", ""]
    if not events:
        lines.append("Новых подходящих событий не нашлось.")
    for e in events:
        t = e.start.astimezone(TZ)
        when = f"{WEEKDAYS[t.weekday()]}, {t.day} {MONTHS[t.month - 1]}, {t:%H:%M}"
        lines.append(f'<b>{when}</b>: <a href="{escape(e.url)}">{escape(e.title)}</a>')
        place = escape(e.location) if e.location else "место не указано"
        lines.append(f"📍 {place}" + (f" · {escape(e.price)}" if e.price else ""))
        if e.why:
            lines.append(escape(e.why))
        lines.append("")
    lines.append(
        f"<i>Страниц проверено: {checked}, отклонено: {rejected}. "
        f"Токены: {usage.input_tokens:,} вх / {usage.output_tokens:,} вых, поисков: {usage.searches}.</i>"
    )
    return "\n".join(lines)


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit and current:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append(current)
    return chunks


def send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    with httpx.Client(timeout=20) as client:
        for chunk in split_message(text):
            r = client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            r.raise_for_status()
