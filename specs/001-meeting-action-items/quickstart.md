# Quickstart: Meeting Action Item Extraction

Validation guide proving the feature works. Contract: [contracts/openapi.yaml](./contracts/openapi.yaml).
Data shapes: [data-model.md](./data-model.md).

## Prerequisites

- Python 3.12, or Docker
- Access to an LLM provider with an OpenAI-compatible API that supports JSON mode: its base URL,
  an API key, and a model name (only for running the real service; tests need none of these)

## 1. Run the tests (no API key, no network)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

**Expected**: all tests pass. They cover user stories 1–3 with a fake LLM, plus schema
validation of good and bad LLM output.

## 2. Run locally

Set the three LLM variables (values below are examples; use your provider's):

```bash
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_API_KEY=...        # never commit this
export LLM_MODEL=your-model-name
uvicorn --factory meeting_actions.main:create_app --port 8000
```

Alternatively copy `.env.example` to `.env`, fill it in, and load it into your shell. `.env` is
git-ignored.

**Expected**: if any of the three variables is missing, the service stops at startup with a
message naming it.

## 3. Run with Docker

```bash
docker build -t meeting-actions .
docker run --rm -p 8000:8000 -e LLM_BASE_URL -e LLM_API_KEY -e LLM_MODEL meeting-actions
# or: docker run --rm -p 8000:8000 --env-file .env meeting-actions
```

The values are passed at run time; none are in the image.

## Switching provider

Change only the three variables and restart; no code change or rebuild. Example for a local
Ollama server: `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_API_KEY=ollama` (any non-empty
value), `LLM_MODEL=<a model you have pulled>`.

## 4. Validation scenarios

| # | Request body | Expected |
|---|--------------|----------|
| 1 | `{"notes": "Alice will send the budget report by Friday."}` | 200, one item: task about the budget report, owner `Alice`, due_date `Friday` |
| 2 | `{"notes": "Bob to book the venue."}` | 200, one item, owner `Bob`, due_date `null` |
| 3 | `{"notes": "We reviewed Q3 numbers. Revenue was flat."}` | 200, `{"action_items": []}` |
| 4 | `{"notes": "   "}` | 400, code `empty_notes` |
| 5 | notes of 20,001 characters | 400, code `notes_too_long`, message states limit and length received |
| 6 | `{"text": "hi"}` | 400, code `invalid_request` |

Example:

```bash
curl -s -X POST localhost:8000/v1/action-items \
  -H "Content-Type: application/json" \
  -d '{"notes": "Alice will send the budget report by Friday."}'
```

## 5. Accuracy and latency check (manual, real provider)

With the three `LLM_*` variables set:

```bash
python eval/run_eval.py              # add --delay 5 if the provider rate-limits requests
```

**Expected**: the script prints per-sample results from `eval/samples.json` and four totals:
recall ≥ 0.90 (SC-001), fabrication rate ≤ 0.05 (SC-002), 100% of no-action samples return an
empty list (SC-003), p95 latency < 10 s (SC-005). It exits with code 1 if any target is missed.
This calls the real LLM and costs money; it is not part of `pytest`.

## 6. Privacy check

Send scenario 1, then check the service logs: they show the note length and item count, never
the note text.
