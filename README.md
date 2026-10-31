# Meeting Actions

A small HTTP service that takes meeting notes as text and returns the action items in them:
the task, the owner, and the due date (as written), with `null` when the notes don't say.
Notes are not stored or logged.

It works with any LLM provider that offers an OpenAI-compatible API with JSON mode.

## Configuration

Set three environment variables (see `.env.example`):

| Variable | Example |
|----------|---------|
| `LLM_BASE_URL` | `https://api.openai.com/v1` |
| `LLM_API_KEY` | your provider's key (never commit it) |
| `LLM_MODEL` | the model name at that provider |

The service stops at startup if any of them is missing. To switch provider, change the
variables and restart.

## API

`POST /v1/action-items` with `{"notes": "..."}` (1 to 20,000 characters after trimming).

- `200` → `{"action_items": [{"task": "...", "owner": "..." | null, "due_date": "..." | null}]}`
- `400` → `empty_notes`, `notes_too_long`, or `invalid_request`
- `502` → `extraction_failed` (the LLM call failed or its reply did not match the schema)

Errors look like `{"error": {"code": "...", "message": "..."}}`. Full contract:
`specs/001-meeting-action-items/contracts/openapi.yaml`.

## Run the tests

No API key or network needed; the LLM is faked.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
mypy src tests eval
```

## Run locally

```bash
export LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=...
uvicorn --factory meeting_actions.main:create_app --port 8000
```

## Run with Docker

```bash
cp .env.example .env    # fill in real values; .env is git-ignored
docker build -t meeting-actions .
docker run --rm -p 8000:8000 --env-file .env meeting-actions
```

## Check accuracy against a real provider

```bash
python eval/run_eval.py              # add --delay 5 if the provider rate-limits requests
```

Runs the sample notes in `eval/samples.json` through the real LLM and reports recall,
fabrication rate, empty-list correctness, and p95 latency against the spec's targets. It costs
API usage and is not part of `pytest`.

More detail: `specs/001-meeting-action-items/quickstart.md`.
