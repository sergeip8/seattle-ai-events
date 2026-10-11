# seattle-ai-events

A small weekly agent that finds technical AI events in the Seattle area and sends a verified shortlist to Telegram. It runs on GitHub Actions every Monday morning.

The interesting part is not the search, it's the **grounding**: every event that reaches the digest has been checked by plain code against the page it came from, so the agent can't invent an event or stitch the date of one meetup onto the title of another.

## How it works

```
discover ──► fetch ──► extract ──► verify ──► notify
 (Claude +    (httpx,    (Claude,    (plain     (Telegram)
 web search)  HTML→text) forced tool) Python)
```

1. **Discover** (`src/discover.py`): Claude with the server-side web search tool looks for event pages and returns **URLs only**. It doesn't describe events at this stage, so there's nothing for later steps to trust blindly.
2. **Fetch** (`src/fetch.py`): code downloads each page and reduces it to text, keeping the JSON-LD block, which often has `name`/`startDate`/`location` even on JavaScript-heavy pages.
3. **Extract** (`src/extract.py`): a cheaper model reads one page and fills a strict schema via a forced tool call: title, start time, venue, price, and a verbatim `evidence` snippet containing the date. One page, one event.
4. **Verify** (`src/verify.py`): no LLM. An event is dropped unless:
   - the `evidence` snippet appears **verbatim** on the downloaded page (after whitespace/case normalization),
   - the claimed date appears inside that evidence,
   - the title appears on the page,
   - the date is within the window, the event is technical and in person, and it hasn't been sent before.
5. **Notify** (`src/notify.py`): formats the digest and sends it to Telegram. Token and search usage are included in every message.

Already-sent events are stored in `data/seen.json`, which the workflow commits back to the repo.

## Setup

### 1. Telegram bot (5 minutes)

1. In Telegram, message [@BotFather](https://t.me/BotFather), send `/newbot`, and pick a name. Copy the **token**.
2. Send any message to your new bot.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy `message.chat.id`. That's your **chat ID**.

### 2. Repository secrets

```bash
gh secret set ANTHROPIC_API_KEY
gh secret set TELEGRAM_BOT_TOKEN
gh secret set TELEGRAM_CHAT_ID
```

Set a monthly spend limit in the Claude Console as well.

### 3. First run

Actions → **weekly-events** → **Run workflow**. `dry_run` is on by default for manual runs, so the digest is printed in the log instead of being sent. Untick it to send a real message.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q

export ANTHROPIC_API_KEY=...
python src/main.py --dry-run          # prints the digest and rejection reasons
python src/main.py --days 7           # sends to Telegram (needs TELEGRAM_* vars)
```

Models are configurable with `DISCOVER_MODEL` (default `claude-sonnet-5-5`) and `EXTRACT_MODEL` (default `claude-haiku-5-5`).

## Cost

One weekly run is roughly 8 web searches plus ~25 extraction calls on a small model. Every digest ends with the exact token and search counts, so you can track it over time.

## Ideas for v2

- An LLM verifier for semantic checks (e.g. "is this really an AI event?"), given the page text and asked to label each field supported / contradicted / not found.
- An eval set: a fixed list of real event pages and hand-labeled expected fields, to measure extraction accuracy when changing models or prompts.
- Compare the digest against an independent baseline run to measure recall.
