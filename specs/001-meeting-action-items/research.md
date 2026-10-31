# Research: Meeting Action Item Extraction

All Technical Context items were specified by the user or resolved below. No open
NEEDS CLARIFICATION items remain.

## 1. LLM provider and SDK

- **Decision**: Any provider that exposes an OpenAI-compatible Chat Completions API, called
  through the official `openai` Python SDK with a configurable `base_url`.
- **Rationale**: The user wants to change provider without code changes. Many providers and
  self-hosted servers (OpenAI, Azure OpenAI, Groq, Together, DeepSeek, Ollama, vLLM, and
  others) accept the same request shape, so one client covers them all; switching is a matter
  of changing three environment variables.
- **Alternatives considered**: A vendor SDK such as `anthropic` (ties the code to one
  provider); raw HTTP with `httpx` (more code, no typed errors or retries);
  multi-provider frameworks such as LangChain or LiteLLM (extra dependencies, against
  Simplicity).

## 2. Model choice

- **Decision**: No model is hard-coded. The model name comes from `LLM_MODEL` and is passed
  through unchanged. No sampling parameters (`temperature`, `top_p`) are sent.
- **Rationale**: Model names differ per provider, so any default would be wrong for most of
  them. Some models reject sampling parameters, so leaving them out keeps every provider
  working.
- **Alternatives considered**: A default model name (only valid for one provider).

## 3. JSON output and validation

- **Decision**: Call `client.chat.completions.create(...)` with
  `response_format={"type": "json_object"}`, and put the JSON shape (generated from the
  `ExtractionResult` Pydantic model) in the system prompt. Validate the reply with
  `ExtractionResult.model_validate_json(content)`.
- **Failure handling** (all map to `ExtractionError` → HTTP 502 `extraction_failed`):
  - `finish_reason == "length"` (output cut off), or a reply that is a refusal or has no content;
  - content that is not valid JSON or fails Pydantic validation (`ValidationError`);
  - SDK errors (`openai.APIError` subclasses: connection, timeout, status errors).
- **Rationale**: JSON mode (`json_object`) is the most widely supported structured-output
  option across OpenAI-compatible providers. The app's own Pydantic validation is what the
  constitution requires (Principle III), so it holds no matter how strictly a provider
  follows the schema.
- **Alternatives considered**: `response_format` of type `json_schema` with `strict: true`, or
  the SDK's `chat.completions.parse` helper (stronger guarantees, but many compatible
  providers reject or ignore them, which would break the "change provider without code
  changes" goal); tool/function calling (more code, and also unevenly supported).

## 4. Timeouts and retries

- **Decision**: Set a 15-second request timeout and 1 retry (`max_retries=1`) on the SDK
  client. No extra retry logic in the app.
- **Rationale**: Keeps the worst-case wait before an `extraction_failed` response to about
  30 seconds plus a short backoff, instead of about 90 seconds with a 30-second timeout and
  2 retries, while still covering one brief provider hiccup. A 15-second timeout leaves room
  for the SC-005 target (under 10 seconds for 95% of requests). Callers can retry an
  `extraction_failed` themselves.

## 5. Testing the LLM boundary

- **Decision**: Define `Extractor` as a `typing.Protocol` with
  `extract(notes: str) -> list[ActionItem]`. The app is built by
  `create_app(extractor: Extractor | None = None)`: tests pass a `FakeExtractor` that returns
  canned items or raises `ExtractionError`; in production `create_app()` builds an
  `OpenAICompatibleExtractor` from the environment. `OpenAICompatibleExtractor` is tested by
  passing in a stub object that mimics `client.chat.completions.create`.
- **Rationale**: Constitution I forbids live LLM calls in tests. Passing the extractor in keeps
  tests free of environment variables and of any mocking library.
- **Alternatives considered**: `unittest.mock.patch` on the SDK (brittle); recorded HTTP
  cassettes with `vcrpy` (extra dependency); FastAPI `dependency_overrides` (works, but the app
  would still need configuration to import).

## 6. Input validation and error format

- **Decision**: The route trims the notes and checks empty / >20,000 characters before calling
  the extractor, raising an app-level error. A single error shape
  `{"error": {"code": str, "message": str}}` is used for all errors, including FastAPI's request
  validation errors (mapped to `invalid_request`).
- **Status codes**: 400 for `empty_notes`, `notes_too_long`, `invalid_request`; 502 for
  `extraction_failed`.
- **Rationale**: FR-007–FR-009 need specific messages and stable codes; doing the check in one
  place keeps messages exact (e.g. "received 20,001").
- **Alternatives considered**: Pydantic `Field(min_length, max_length)` on the request (FastAPI
  would return its generic 422 body, not the clear message the spec requires).

## 7. Not storing notes

- **Decision**: No persistence layer; notes are never written to logs. Logging records only
  request outcome, note length, item count, and latency.
- **Rationale**: FR-012. The configured LLM provider still receives the notes to process them
  (documented assumption in the spec); its own data-retention terms apply.

## 8. Configuration and secrets

- **Decision**: `config.py` reads three required environment variables with `os.environ`:
  - `LLM_BASE_URL`: the provider's OpenAI-compatible endpoint, e.g. `https://api.openai.com/v1`;
  - `LLM_API_KEY`: the provider's API key;
  - `LLM_MODEL`: the model name at that provider.
  `create_app()` reads them at startup and stops with a clear message naming any missing
  variable, so a misconfigured container fails immediately instead of on the first request.
  A `.env.example` lists all three with placeholder values; `.env` is git-ignored and excluded
  by `.dockerignore`. Values are passed at `docker run` time.
- **Rationale**: Constitution IV, plus provider changes need no code change. Plain `os.environ`
  avoids a `pydantic-settings` dependency for three variables.
- **Alternatives considered**: `pydantic-settings` (one more dependency); provider-specific
  variable names such as `OPENAI_API_KEY` (misleading when the provider is not OpenAI).

## 9. Container

- **Decision**: `python:3.12-slim` base, install the package with pip, run
  `uvicorn --factory meeting_actions.main:create_app` on port 8000 as a non-root user.
  Single stage.
- **Rationale**: Small, standard, and enough for a pure-Python service.
- **Alternatives considered**: Multi-stage build or distroless image (more complexity for little
  gain at this size).

## 10. Due-date format

- **Decision**: Due dates are returned **as written**, with no calendar conversion (FR-004).
  Recorded in the spec's Clarifications section (Session 2026-10-30).
- **Note**: Changing this later would add a field to `ActionItem` and an optional meeting date
  to the request.

## 11. Measuring accuracy and latency

- **Decision**: A manual evaluation script, `eval/run_eval.py`, runs the real
  `OpenAICompatibleExtractor` (configured from the `LLM_*` variables) over a reference set in
  `eval/samples.json` and reports recall (SC-001), fabrication rate (SC-002), empty-list
  correctness (SC-003), and p95 latency (SC-005). Expected and returned items are matched by
  same owner (case-insensitive, `null` equals `null`) and task similarity of at least 0.6 using
  the standard library's `difflib.SequenceMatcher`.
- **Rationale**: These targets depend on real model behavior, so the pytest fake cannot measure
  them, and the constitution forbids live LLM calls in tests. Keeping the script outside
  `tests/` means `pytest` never runs it. Standard library only, so no new dependency.
- **Alternatives considered**: An LLM-as-judge grader (extra cost and complexity); exact string
  matching on tasks (too strict, since the model may rephrase slightly); a pytest marker for live
  tests (easy to run by accident, and blurs the "no live LLM in tests" rule).
