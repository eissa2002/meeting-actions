---

description: "Task list for Meeting Action Item Extraction"
---

# Tasks: Meeting Action Item Extraction

**Input**: Design documents from `/specs/001-meeting-action-items/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: Required. The constitution (Principle I) says every feature MUST have pytest tests,
and tests MUST NOT call a live LLM. Within each story, write the tests first and confirm they
fail before implementing.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Single project: `src/meeting_actions/` and `tests/` at the repository root

## Shared rules for every task

- Python 3.12, full type hints on every function and method (Principle II); avoid `Any`.
- No secrets anywhere in code, tests, or fixtures (Principle IV). Tests use fake values such as
  `"test-key"`.
- Never log or store the notes text (FR-012).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create `pyproject.toml` at the repo root: project name `meeting-actions`, `requires-python = ">=3.12"`, src layout with package `meeting_actions` in `src/`, runtime dependencies `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `openai`; optional `dev` extra with `pytest`, `mypy` (FastAPI `TestClient` uses `httpx2`, installed by `openai`); `[tool.pytest.ini_options] testpaths = ["tests"]`; `[tool.mypy] strict = true`
- [X] T002 [P] Create `.gitignore` ignoring `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `*.egg-info/`
- [X] T003 [P] Create `.env.example` with exactly three placeholder lines: `LLM_BASE_URL=https://api.example.com/v1`, `LLM_API_KEY=your-key-here`, `LLM_MODEL=your-model-name`
- [X] T004 [P] Create empty `src/meeting_actions/__init__.py` and an empty `tests/` directory

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Models, configuration, the extractor interface, the app factory, and test fixtures that every story uses

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Write schema tests in `tests/test_models.py`: `ExtractionResult.model_validate_json` accepts `{"action_items": []}` and items with `owner`/`due_date` set to strings or `null`; rejects missing `action_items`, an item missing `task`, `task` of `""` or whitespace only, `owner` as a number, and non-JSON text (Principle III)
- [X] T006 Implement `src/meeting_actions/models.py` per data-model.md: constant `MAX_NOTES_CHARS = 20_000`; `ActionItem` with `task: str` ("Required, non-empty after trimming" — strip and reject empty via a field validator), `owner: str | None` ("`null` when not specified"), `due_date: str | None` ("as written in the notes … `null` when not specified"), all three fields required in JSON (no defaults, so the LLM must state `null` explicitly); `ExtractionResult(action_items: list[ActionItem])`; `ExtractRequest(notes: str)` with no length constraints (checked in the route); `ExtractResponse(action_items: list[ActionItem])`; `ErrorDetail(code: str, message: str)`; `ErrorResponse(error: ErrorDetail)`
- [X] T007 [P] Write config tests in `tests/test_config.py`: `load_settings` returns a `Settings` with the three values from a given mapping; raises `ConfigError` whose message names every missing variable when any of `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` is absent or an empty string
- [X] T008 [P] Implement `src/meeting_actions/config.py`: frozen dataclass `Settings(base_url: str, api_key: str, model: str)`; `class ConfigError(Exception)`; `load_settings(env: Mapping[str, str] = os.environ) -> Settings` that reads `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, treats empty strings as missing, and raises `ConfigError("Missing required environment variables: ...")` listing all missing names
- [X] T009 Create `src/meeting_actions/extractor.py` with `class ExtractionError(Exception)` and `class Extractor(Protocol)` declaring `def extract(self, notes: str) -> list[ActionItem]: ...`
- [X] T010 Create `src/meeting_actions/main.py` with: `class AppError(Exception)` holding `status_code: int`, `code: str`, `message: str`; an exception handler that returns `ErrorResponse` JSON with the error's status code; `GET /health` returning `{"status": "ok"}`; and `create_app(extractor: Extractor | None = None) -> FastAPI` that stores the extractor on the app (the `None` branch is completed in T016)
- [X] T011 Create `tests/conftest.py` with `FakeExtractor` (constructed with `items: list[ActionItem] | None = None` and `error: Exception | None = None`; records every `notes` it receives in `self.calls`; raises `error` if set, else returns `items or []`) and a `make_client` fixture returning a factory `(FakeExtractor) -> TestClient` built with `create_app(extractor=fake)`

**Checkpoint**: `pytest tests/test_models.py tests/test_config.py` passes; the app starts in tests and `GET /health` works

---

## Phase 3: User Story 1 - Extract action items from meeting notes (Priority: P1) 🎯 MVP

**Goal**: `POST /v1/action-items` returns the action items (task, owner, due date) found in the notes, using any OpenAI-compatible LLM

**Independent Test**: With a fake extractor returning known items, the endpoint returns them unchanged and in order; with a stubbed OpenAI client, the extractor turns a valid JSON reply into items and turns every bad reply into `ExtractionError`

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T012 [P] [US1] Write API tests in `tests/test_api.py`: (a) a fake returning two items → 200 with `{"action_items": [...]}` in the same order; (b) an item with `owner` and `due_date` of `None` is returned as JSON `null`; (c) the fake receives the notes with leading/trailing whitespace trimmed; (d) the fake raising `ExtractionError` → 502 with `{"error": {"code": "extraction_failed", "message": "Could not extract action items. Please try again."}}`; (e) using pytest's `caplog`, the notes text never appears in log output for success or failure; (f) `GET /health` → 200 `{"status": "ok"}`
- [X] T013 [P] [US1] Write extractor tests in `tests/test_extractor.py` using a stub object with a `chat.completions.create(**kwargs)` method that records kwargs and returns a canned response built from `SimpleNamespace` (`choices[0].message.content`, `choices[0].message.refusal`, `choices[0].finish_reason`), or raises: (a) a valid JSON reply → the parsed `list[ActionItem]`; (b) the request uses `model` from the constructor, `response_format={"type": "json_object"}`, a system message that contains the JSON schema of `ExtractionResult`, a user message containing the notes, and sends no `temperature` or `top_p`; each of these → `ExtractionError`: (c) `finish_reason == "length"`, (d) `content is None`, (e) `refusal` set, (f) content that is not JSON, (g) JSON that fails the schema, (h) the stub raising `openai.APIConnectionError(request=httpx2.Request("POST", "https://test"))`; (i) `OpenAICompatibleExtractor.from_settings(Settings("https://test/v1", "test-key", "m"))` builds without network access. Pass the stub to the constructor as `typing.cast(OpenAI, stub)` so strict mypy passes without using `Any` (Principle II)

### Implementation for User Story 1

- [X] T014 [US1] Implement `OpenAICompatibleExtractor` in `src/meeting_actions/extractor.py`: `__init__(self, client: OpenAI, model: str)`; classmethod `from_settings(settings: Settings) -> OpenAICompatibleExtractor` creating `OpenAI(base_url=settings.base_url, api_key=settings.api_key, timeout=15.0, max_retries=1)` (keeps a failing call to about 30 s worst case; see research.md §4); module constant `SYSTEM_PROMPT` that tells the model to return only a JSON object matching the embedded `ExtractionResult.model_json_schema()`, to list action items in the order they appear, to create one item per owner when a task has several owners, to copy owner names and due dates exactly as written, and to use `null` when an owner or due date is not stated
- [X] T015 [US1] Implement `OpenAICompatibleExtractor.extract(notes: str) -> list[ActionItem]` in `src/meeting_actions/extractor.py`: call `client.chat.completions.create(model=..., messages=[system, user], response_format={"type": "json_object"})` with no sampling parameters; raise `ExtractionError` on any `openai.APIError`, `finish_reason == "length"`, a set `refusal`, `None`/empty content, or a `pydantic.ValidationError` from `ExtractionResult.model_validate_json(content)`; otherwise return `result.action_items`. Never include the notes in exception messages
- [X] T016 [US1] In `src/meeting_actions/main.py`, add `POST /v1/action-items` taking `ExtractRequest` and returning `ExtractResponse`: trim `notes`, call the app's extractor, map `ExtractionError` to `AppError(502, "extraction_failed", "Could not extract action items. Please try again.")`; complete `create_app`: when `extractor` is `None`, call `load_settings()` and use `OpenAICompatibleExtractor.from_settings(...)`, so missing variables fail at startup with the `ConfigError` message
- [X] T017 [US1] Add logging in `src/meeting_actions/main.py` using the standard `logging` module: one line per request with outcome (`ok` or the error code), note length in characters, item count, and latency in ms, and never the notes text (FR-012)

**Checkpoint**: `pytest` passes; with real `LLM_*` variables, quickstart scenarios 1 and 2 work

---

## Phase 4: User Story 2 - Notes with no action items (Priority: P2)

**Goal**: Notes with no commitments return a successful empty list, never an error or invented items

**Independent Test**: A fake returning no items → 200 `{"action_items": []}`; a stubbed LLM reply of `{"action_items": []}` → `[]`

### Tests for User Story 2 ⚠️

- [X] T018 [P] [US2] Add to `tests/test_api.py`: a fake returning `[]` → 200 with body exactly `{"action_items": []}`
- [X] T019 [P] [US2] Add to `tests/test_extractor.py`: a stub reply of `{"action_items": []}` → `extract` returns `[]` with no error; `SYSTEM_PROMPT` contains the instruction to return an empty list and not to invent items

### Implementation for User Story 2

- [X] T020 [US2] Extend `SYSTEM_PROMPT` in `src/meeting_actions/extractor.py`: "Only include tasks someone committed to or was assigned in the notes; do not invent items. If there are none, return {\"action_items\": []}." (FR-006, FR-010)

**Checkpoint**: User Stories 1 and 2 pass; quickstart scenario 3 returns an empty list

---

## Phase 5: User Story 3 - Clear errors for invalid input (Priority: P3)

**Goal**: Empty, whitespace-only, over-limit, or malformed requests get a clear 400 error with a stable code, and the LLM is never called

**Independent Test**: Each invalid request returns the documented code and message from data-model.md, and the fake extractor's `calls` stays empty

### Tests for User Story 3 ⚠️

- [X] T021 [US3] Add to `tests/test_api.py`, each asserting the fake was not called: (a) `{"notes": ""}` → 400 `empty_notes`, message `"Notes must not be empty."`; (b) `{"notes": "  \n\t "}` → same; (c) `"a" * 20_000` → 200 (accepted at the limit); (d) `"a" * 20_001` → 400 `notes_too_long`, message `"Notes must be at most 20,000 characters; received 20,001."`; (e) `" " + "a" * 20_000 + " "` → 200 (length measured after trimming); (f) `{"text": "hi"}`, (g) `{"notes": 123}`, (h) a non-JSON body → 400 `invalid_request`, message `"Request body must be JSON with a 'notes' string field."`

### Implementation for User Story 3

- [X] T022 [US3] In the `POST /v1/action-items` handler in `src/meeting_actions/main.py`, before calling the extractor: after trimming, if empty raise `AppError(400, "empty_notes", "Notes must not be empty.")`; if `len(notes) > MAX_NOTES_CHARS` raise `AppError(400, "notes_too_long", f"Notes must be at most {MAX_NOTES_CHARS:,} characters; received {len(notes):,}.")`
- [X] T023 [US3] In `create_app` in `src/meeting_actions/main.py`, register a handler for FastAPI's `RequestValidationError` returning 400 `ErrorResponse` with code `invalid_request` and message `"Request body must be JSON with a 'notes' string field."` (does not echo the request body)

**Checkpoint**: All three user stories pass; quickstart scenarios 4–6 return the documented errors

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Packaging, documentation, and final checks across all stories

- [X] T024 [P] Create `Dockerfile`: base `python:3.12-slim`, `WORKDIR /app`, copy `pyproject.toml` and `src/`, `pip install --no-cache-dir .`, create and switch to a non-root user, `EXPOSE 8000`, `CMD ["uvicorn", "--factory", "meeting_actions.main:create_app", "--host", "0.0.0.0", "--port", "8000"]`; no `ENV` or `ARG` for any `LLM_*` value
- [X] T025 [P] Create `.dockerignore` excluding `.env`, `.git/`, `.venv/`, `tests/`, `eval/`, `specs/`, `.specify/`, `.claude/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`
- [X] T026 [P] Create a short `README.md`: what the service does, the three `LLM_*` variables, how to run tests, run locally, run with Docker, and run the evaluation script (link to `specs/001-meeting-action-items/quickstart.md` for details)
- [X] T027 [P] Create the reference set `eval/samples.json` (SC-001, SC-002, SC-003): a JSON list of 15 entries `{"id": str, "notes": str, "expected": [{"task": str, "owner": str | null, "due_date": str | null}]}`, all invented (no real people, companies, or meeting content). Cover: single item with owner and due date; several items in order; missing owner; missing due date; one task with two owners (expects two items); relative due date kept as written ("next Tuesday"); discussion-only notes with `"expected": []` (at least 3 entries); a distractor sentence that sounds like a task but is not one ("We could maybe look at pricing someday"); one entry not in English
- [X] T028 Create `eval/run_eval.py`, a manual script run as `python eval/run_eval.py`, outside `tests/` so pytest never collects it, using only the standard library and the app's own code: load settings with `load_settings()` and build `OpenAICompatibleExtractor.from_settings(...)`; for each sample, time `extract(notes)` and catch `ExtractionError` (count as a failed sample); match returned items to expected items one-to-one, where a match means the same owner (case-insensitive, `null` equals `null`) and `difflib.SequenceMatcher(None, expected_task.lower(), returned_task.lower()).ratio() >= 0.6`; print per-sample results by `id` and four totals: recall = matched expected / total expected (target ≥ 0.90, SC-001), fabrication rate = unmatched returned / total returned (target ≤ 0.05, SC-002), empty-list samples answered with `[]` (target 100%, SC-003), and p95 latency in seconds (target < 10, SC-005); exit with code 1 if any target is missed. Never print the API key. Fully type-hinted
- [X] T029 Run `pytest` and `mypy src tests eval`; fix any failures until both are clean
- [X] T030 Check for secrets: search the repo (excluding `.env`) for API-key patterns such as `sk-` and confirm `.env` is listed in `.gitignore` and `.dockerignore`
- [ ] T031 Run the manual checks against a real provider (needs real `LLM_*` values in `.env`): `docker build`, quickstart.md scenarios 1–6 using `--env-file .env`, the log privacy check, and `python eval/run_eval.py`; record the four eval totals, and if a target is missed, adjust `SYSTEM_PROMPT` or the model and re-run

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; start immediately
- **Foundational (Phase 2)**: Depends on Setup; BLOCKS all user stories
- **User Stories (Phases 3–5)**: Depend on Foundational
- **Polish (Phase 6)**: T024–T027 can start after Foundational; T028 needs `extractor.py` from US1 (T015); T029–T031 need all stories and T027–T028 done

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational; no dependency on other stories
- **US2 (P2)**: T018 needs only Foundational. T019 and T020 edit `extractor.py`/`test_extractor.py` after US1 creates them (T013, T014)
- **US3 (P3)**: T021 and T023 need only Foundational. T022 adds checks to the route created in T016, so do it after US1

### Within Each Phase

- Tests before implementation, and they must fail first
- T005 → T006; T007 → T008; T006 → T009 → T010 → T011
- T014 → T015 → T016 → T017
- Tasks editing the same file run one at a time: `main.py` (T010, T016, T017, T022, T023), `extractor.py` (T009, T014, T015, T020), `tests/test_api.py` (T012, T018, T021)

### Parallel Opportunities

- Phase 1: T002, T003, T004 together after T001
- Phase 2: T005 and T007 together, then T006 and T008 together
- US1: T012 and T013 together (different test files)
- US2: T018 and T019 together
- Polish: T024, T025, T026, T027 together

---

## Parallel Example: User Story 1

```bash
# Write both test files for User Story 1 together:
Task: "Write API tests in tests/test_api.py (T012)"
Task: "Write extractor tests in tests/test_extractor.py (T013)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `pytest` passes; try quickstart scenarios 1–2 with a real provider
5. Demo if ready

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add US1 → test → MVP
3. Add US2 → test (empty list behaviour)
4. Add US3 → test (input errors)
5. Polish → Docker image, README, evaluation set and script, final checks

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate a story on its own
