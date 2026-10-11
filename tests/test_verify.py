from datetime import datetime

from fetch import html_to_text
from models import TZ
from verify import verify

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=TZ)

PAGE = """
PAGE TITLE: AI Agents Builders Night
PAGE TEXT:
AI Agents Builders Night
Tuesday, October 13, 2026
6:00 PM - 9:00 PM
The Collective, 400 Dexter Ave N, Seattle
Lightning demos of agent frameworks, followed by Q&A.
"""


def good(**overrides):
    data = {
        "is_event_page": True,
        "title": "AI Agents Builders Night",
        "start_iso": "2026-10-13T18:00:00-07:00",
        "location": "The Collective, Seattle",
        "price": "",
        "is_technical_ai": True,
        "is_in_person": True,
        "evidence": "Tuesday, October 13, 2026",
        "why": "Демо агентных фреймворков",
    }
    data.update(overrides)
    return data


def run(data, page=PAGE, seen=frozenset()):
    return verify(data, "https://lu.ma/x", page, NOW, 14, set(seen))


def test_accepts_grounded_event():
    event, reasons = run(good())
    assert event is not None, reasons
    assert event.start.day == 13


def test_rejects_invented_evidence():
    _, reasons = run(good(evidence="Thursday, October 15, 2026"))
    assert "evidence_not_on_page" in reasons


def test_rejects_date_stitched_from_another_event():
    # Evidence is real, but the claimed date doesn't match it.
    _, reasons = run(good(start_iso="2026-10-15T18:00:00-07:00"))
    assert "date_not_in_evidence" in reasons


def test_rejects_title_not_on_page():
    _, reasons = run(good(title="Seattle LLM Hackathon"))
    assert "title_not_on_page" in reasons


def test_rejects_past_and_far_future():
    assert "outside_window" in run(good(start_iso="2026-10-01T18:00:00-07:00"))[1]
    assert "outside_window" in run(good(start_iso="2026-12-01T18:00:00-08:00"))[1]


def test_whitespace_and_case_differences_are_ok():
    event, reasons = run(good(evidence="tuesday,   OCTOBER 13,\n2026"))
    assert event is not None, reasons


def test_json_ld_utc_date_is_accepted():
    # 6pm PDT on Oct 13 is Oct 14 01:00 UTC; JSON-LD often stores UTC.
    page = PAGE + '\nSTRUCTURED DATA (JSON-LD):\n{"startDate":"2026-10-14T01:00:00.000Z"}'
    event, reasons = run(good(evidence='"startDate":"2026-10-14T01:00:00.000Z"'), page=page)
    assert event is not None, reasons


def test_rejects_non_technical_and_seen():
    assert "not_technical_ai" in run(good(is_technical_ai=False))[1]
    assert "already_sent" in run(good(), seen={"https://lu.ma/x"})[1]


def test_listing_page_is_rejected():
    assert run(good(is_event_page=False))[1] == ["not_an_event_page"]


def test_html_to_text_keeps_json_ld():
    html = """<html><head><title>Demo Night</title>
    <script type="application/ld+json">{"@type":"Event","startDate":"2026-10-13T18:00"}</script>
    <script>var x = 1;</script></head>
    <body><nav>Menu</nav><h1>Demo Night</h1><p>Oct 13</p></body></html>"""
    text = html_to_text(html)
    assert "PAGE TITLE: Demo Night" in text
    assert '"startDate":"2026-10-13T18:00"' in text
    assert "var x" not in text
    assert "Menu" not in text
