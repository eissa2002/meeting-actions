# Implementation Plan: Meeting Action Item Extraction

**Branch**: `001-meeting-action-items` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-meeting-action-items/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A small stateless HTTP service with one endpoint: it accepts meeting notes as text and returns
the action items found in them (task, owner, due date). Input is checked for empty and
too-long text before any LLM call. The LLM is any provider with an OpenAI-compatible API,
called through the `openai` Python SDK; its endpoint, key, and model come from the
`LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` environment variables, so the provider can change
without code changes. The LLM is asked for JSON; the reply is validated against a Pydantic
schema and any failure becomes a clear `extraction_failed` error. Notes are never stored or
logged. The LLM sits behind a small interface so pytest uses a fake. Shipped as a Docker image.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, Uvicorn, Pydantic v2, `openai` (official SDK, used with a
configurable base URL for any OpenAI-compatible provider)

**Development Dependencies** (dev extra only; not installed in the Docker image):
`pytest` (required test framework, Principle I); `mypy` in strict mode (checks that all code is
fully type-hinted, Principle II; the standard library has no type checker). FastAPI's
`TestClient` and the SDK error objects used in tests rely on `httpx2`, which the `openai`
package already installs, so no separate HTTP client is added

**Storage**: N/A (stateless; notes are not persisted or logged — FR-012)

**Testing**: pytest with FastAPI `TestClient` and a fake extractor; no live LLM calls.
Accuracy (SC-001, SC-002) and latency (SC-005) are measured separately by a manual evaluation
script in `eval/` that calls a real provider; it is not part of the pytest suite

**Target Platform**: Linux container (Docker)

**Project Type**: web-service (single project)

**Performance Goals**: 95% of requests with notes under 2,000 words answered in under 10 s (SC-005)

**Constraints**: Notes limited to 20,000 characters; LLM output must pass schema validation;
LLM endpoint, key, and model only from the `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`
environment variables; must work with any OpenAI-compatible provider that supports JSON mode

**Scale/Scope**: Internal use, low traffic; one endpoint plus a health check

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies | Status |
|-----------|------------------------|--------|
| I. Tested Features (pytest) | Every user story has pytest tests; the app takes the extractor as a parameter so tests pass in a fake; the OpenAI-compatible adapter is tested with a stubbed client | PASS |
| II. Typed Code | All functions annotated; request/response/LLM data are Pydantic models; extractor is a typed `Protocol` | PASS |
| III. Schema-Validated LLM Output | The app validates every LLM reply itself with `ExtractionResult.model_validate_json`, independent of how strictly the provider follows JSON mode; invalid JSON, schema mismatch, cut-off or refused output → `extraction_failed` (502), never partial items; schema has valid/invalid tests | PASS |
| IV. No Secrets in Code | `LLM_API_KEY` (and `LLM_BASE_URL`, `LLM_MODEL`) read from the environment; `.env` git-ignored; `.env.example` with placeholders only; nothing baked into the Docker image | PASS |
| V. Simplicity | One package, four modules, one endpoint; no database, queue, cache, auth, or retry framework; only four runtime dependencies; each dev dependency justified under Technical Context; the evaluation script uses only the standard library and the app's own code | PASS |

**Post-design re-check (after Phase 1)**: PASS — the data model, contract, and quickstart add
no new components or dependencies.

## Project Structure

### Documentation (this feature)

```text
specs/001-meeting-action-items/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml     # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/meeting_actions/
├── __init__.py
├── main.py          # create_app() factory, POST /v1/action-items, GET /health, error handlers
├── models.py        # Pydantic models: request, ActionItem, responses, LLM schema
├── extractor.py     # Extractor Protocol, OpenAICompatibleExtractor, prompt, ExtractionError
└── config.py        # LLM_BASE_URL / LLM_API_KEY / LLM_MODEL read from the environment

tests/
├── conftest.py      # FakeExtractor + TestClient fixture via create_app(extractor=...)
├── test_api.py      # User stories 1–3 end to end through the HTTP layer
├── test_models.py   # Schema accepts valid / rejects invalid LLM output
├── test_extractor.py# OpenAICompatibleExtractor with a stubbed SDK client (success, bad JSON,
│                    # schema mismatch, cut-off output, API error)
└── test_config.py   # Missing environment variables produce a clear startup error

eval/                # Manual accuracy/latency check against a real provider (not run by pytest)
├── samples.json     # Reference set: sample notes with expected action items
└── run_eval.py      # Reports recall (SC-001), fabrication rate (SC-002), p95 latency (SC-005)

pyproject.toml       # Dependencies, pytest config
Dockerfile
.dockerignore
.env.example         # LLM_BASE_URL, LLM_API_KEY, LLM_MODEL with placeholder values
.gitignore           # includes .env
```

**Structure Decision**: Single Python package under `src/meeting_actions` with a flat module
layout and a flat `tests/` folder. The project is one small service, so no sub-packages or
separate unit/integration folders.

## Complexity Tracking

No constitution violations; nothing to justify.
