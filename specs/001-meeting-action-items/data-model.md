# Data Model: Meeting Action Item Extraction

All entities are Pydantic v2 models in `src/meeting_actions/models.py`. Nothing is persisted.

## ExtractRequest (HTTP request body)

| Field | Type | Rules |
|-------|------|-------|
| `notes` | `str` | Required. After trimming whitespace: length ≥ 1 (else `empty_notes`) and ≤ 20,000 characters (else `notes_too_long`). Checked in the route, not by Pydantic constraints, so the error messages match the spec. |

## ActionItem

| Field | Type | Rules |
|-------|------|-------|
| `task` | `str` | Required, non-empty after trimming. What must be done. |
| `owner` | `str \| None` | Person's name as written in the notes; `null` when not specified (FR-003). |
| `due_date` | `str \| None` | Due date as written in the notes, e.g. "Friday" (FR-004); `null` when not specified. |

- One item per owner when a task is assigned to several people.
- Items keep the order they appear in the notes (FR-005).

## ExtractionResult (LLM output schema)

| Field | Type | Rules |
|-------|------|-------|
| `action_items` | `list[ActionItem]` | Required; may be empty (FR-006). |

- Its JSON schema (from `ExtractionResult.model_json_schema()`) is included in the system
  prompt, and the request uses JSON mode. The app validates every reply with
  `ExtractionResult.model_validate_json` (Constitution III). Invalid JSON, a schema mismatch, or
  cut-off/empty output → `ExtractionError`.
- Shares `ActionItem` with the HTTP response, so validated items are returned as-is.

## ExtractResponse (HTTP 200 body)

| Field | Type | Rules |
|-------|------|-------|
| `action_items` | `list[ActionItem]` | Empty list when none found. |

## ErrorResponse (HTTP 4xx/5xx body)

| Field | Type | Rules |
|-------|------|-------|
| `error.code` | `str` | One of `empty_notes`, `notes_too_long`, `invalid_request`, `extraction_failed`. |
| `error.message` | `str` | Human-readable, actionable message. |

| Code | HTTP | Example message |
|------|------|-----------------|
| `empty_notes` | 400 | "Notes must not be empty." |
| `notes_too_long` | 400 | "Notes must be at most 20,000 characters; received 20,001." |
| `invalid_request` | 400 | "Request body must be JSON with a 'notes' string field." |
| `extraction_failed` | 502 | "Could not extract action items. Please try again." |

## State

None — each request is independent; no lifecycle or state transitions.
