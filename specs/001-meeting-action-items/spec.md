# Feature Specification: Meeting Action Item Extraction

**Feature Branch**: `001-meeting-action-items`

**Created**: 2026-10-30

**Status**: Draft

**Input**: User description: "Build an API that takes meeting notes as text and returns action items. Each item has the task, the owner, and the due date if mentioned. If there are no action items, return an empty list. If the input is empty or too long, return a clear error."

## Clarifications

### Session 2026-10-30

- Q: When the notes give a due date, should it come back exactly as written, or also as a
  standard calendar date? → A: Exactly as written (e.g. "Friday", "end of Q3"); no calendar
  conversion and no meeting date in the request (see FR-004).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract action items from meeting notes (Priority: P1)

A caller (a person or another system) submits the plain-text notes from a meeting and receives
a list of the action items found in them. Each item states what needs to be done, who owns it,
and when it is due, if the notes say so.

**Why this priority**: This is the core value of the feature; without it nothing else matters.

**Independent Test**: Submit notes containing known action items and confirm the returned list
contains each one with the correct task, owner, and due date.

**Acceptance Scenarios**:

1. **Given** notes stating "Alice will send the budget report by Friday", **When** the notes are
   submitted, **Then** the response contains one item with task "send the budget report", owner
   "Alice", and due date "Friday".
2. **Given** notes containing three distinct action items, **When** the notes are submitted,
   **Then** the response contains exactly three items in the order they appear in the notes.
3. **Given** notes with an action item that names no due date, **When** the notes are submitted,
   **Then** that item is returned with its due date marked as not specified.
4. **Given** notes with an action item that names no owner, **When** the notes are submitted,
   **Then** that item is returned with its owner marked as not specified.

---

### User Story 2 - Notes with no action items (Priority: P2)

A caller submits notes from a meeting where nothing was assigned (e.g., a pure status update)
and receives an empty list rather than an error or invented items.

**Why this priority**: Callers must be able to trust that an empty result means "nothing to do"
and that the system does not fabricate tasks.

**Independent Test**: Submit notes with only discussion and no commitments; confirm the response
is a successful, empty list.

**Acceptance Scenarios**:

1. **Given** notes that contain only discussion and no commitments, **When** the notes are
   submitted, **Then** the response is successful and the list of action items is empty.

---

### User Story 3 - Clear errors for invalid input (Priority: P3)

A caller who submits empty notes, or notes longer than the allowed limit, receives a clear error
explaining what is wrong and how to fix it, and no action items are returned.

**Why this priority**: Protects the system and gives callers actionable feedback, but only
matters once extraction works.

**Independent Test**: Submit empty text and over-limit text separately; confirm each returns a
distinct, readable error and no action items.

**Acceptance Scenarios**:

1. **Given** empty notes, **When** the notes are submitted, **Then** the response is an error
   stating the notes must not be empty.
2. **Given** notes consisting only of whitespace, **When** the notes are submitted, **Then** the
   response is the same "must not be empty" error.
3. **Given** notes longer than the maximum allowed length, **When** the notes are submitted,
   **Then** the response is an error stating the maximum allowed length and the length received.

---

### Edge Cases

- Notes exactly at the maximum length are accepted; one character over is rejected.
- One sentence assigning the same task to several people produces one item per owner.
- A due date written relatively (e.g., "next Tuesday", "end of month") is returned as written,
  not converted to a calendar date.
- Notes in a language other than English: best-effort extraction; no error is raised.
- The extraction step fails or returns unusable results: the caller receives a clear error
  indicating processing failed and may be retried; partial or malformed items are never returned.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept meeting notes as plain text and return a list of action items.
- **FR-002**: Each action item MUST include a task description, an owner, and a due date.
- **FR-003**: When the notes do not name an owner or a due date for an item, that field MUST be
  explicitly marked as not specified rather than guessed.
- **FR-004**: Due dates MUST be returned as they are written in the notes, without conversion.
- **FR-005**: Action items MUST be returned in the order they appear in the notes.
- **FR-006**: When the notes contain no action items, the system MUST return a successful response
  with an empty list.
- **FR-007**: System MUST reject notes that are empty or contain only whitespace, with an error
  message stating the notes must not be empty.
- **FR-008**: System MUST reject notes longer than 20,000 characters, with an error message that
  states the limit and the length received.
- **FR-009**: Error responses MUST be clearly distinguishable from successful responses and MUST
  include a human-readable message and a stable error code.
- **FR-010**: System MUST NOT return action items that are not supported by the notes.
- **FR-011**: If extraction fails or produces results that do not match the expected structure,
  the system MUST return a processing error rather than partial or malformed items.
- **FR-012**: System MUST NOT store submitted notes after the response is returned.

### Key Entities

- **Meeting Notes**: The plain-text input submitted by the caller; between 1 and 20,000
  characters after trimming whitespace.
- **Action Item**: A single commitment found in the notes. Attributes: task (required text),
  owner (person's name as written, or not specified), due date (as written, or not specified).
- **Error**: A failed request outcome. Attributes: error code (e.g., empty input, input too long,
  processing failed) and a human-readable message.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a reference set of sample meeting notes with known action items, at least 90% of
  the expected action items are returned with the correct task, owner, and due date.
- **SC-002**: On the same reference set, no more than 5% of returned items are not present in the
  notes (fabricated items).
- **SC-003**: 100% of notes with no action items return an empty list, not an error.
- **SC-004**: 100% of empty or over-limit submissions return the correct error with a message a
  caller can act on without consulting documentation.
- **SC-005**: Callers receive results for typical notes (under 2,000 words) in under 10 seconds
  in 95% of requests.

## Assumptions

- Callers are internal users or systems; authentication and rate limiting are out of scope for
  this version.
- The maximum input length is 20,000 characters (roughly a one-hour meeting's typed notes).
- Notes are plain text; file uploads, audio, and rich formatting are out of scope.
- Owners are returned as the names written in the notes; no lookup against a user directory.
- Relative due dates are not resolved because the meeting date is not part of the input.
- The feature returns results only; it does not create tasks in other tools or send notifications.
- Extraction relies on an external language model service, which must be available at runtime.
