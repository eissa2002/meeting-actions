<!--
Sync Impact Report
- Version change: (unversioned template) → 1.0.0
- Modified principles (template placeholder → new title):
  - [PRINCIPLE_1_NAME] → I. Tested Features (pytest)
  - [PRINCIPLE_2_NAME] → II. Typed Code
  - [PRINCIPLE_3_NAME] → III. Schema-Validated LLM Output
  - [PRINCIPLE_4_NAME] → IV. No Secrets in Code
  - [PRINCIPLE_5_NAME] → V. Simplicity
- Added sections: Technical Constraints; Development Workflow & Quality Gates
- Removed sections: none
- Templates: dependent templates read this file at runtime; none modified by this command.
- Follow-up TODOs: none
-->

# Meeting Actions Constitution

## Core Principles

### I. Tested Features (pytest)

Every feature MUST ship with pytest tests that exercise its behavior.

- A feature is not complete until its tests exist and pass under `pytest`.
- Bug fixes MUST include a test that reproduces the bug.
- Tests MUST NOT call live LLM APIs or other paid/external services; use fakes or recorded
  responses so the suite is fast and deterministic.

Rationale: tests are the only reliable proof that a feature works and keeps working.

### II. Typed Code

All Python code MUST use type hints.

- Every function and method signature MUST annotate its parameters and return type.
- Data passed between modules MUST use typed structures (e.g. dataclasses or Pydantic models),
  not untyped dicts.
- `Any` MUST be avoided unless justified in a comment.

Rationale: type hints document intent and let tooling catch mistakes before runtime.

### III. Schema-Validated LLM Output

LLM output MUST be validated against an explicit schema before the application uses it.

- Each LLM call that returns structured data MUST have a declared schema (e.g. a Pydantic model).
- Output that fails validation MUST be handled explicitly (retry, error, or rejection); it MUST
  NOT be passed downstream unvalidated.
- Each schema MUST have tests covering both valid and invalid sample output.

Rationale: LLM output is non-deterministic; a schema turns it into a contract the rest of the
code can trust.

### IV. No Secrets in Code

Secrets MUST NOT appear in source code, tests, fixtures, or committed config.

- API keys, tokens, passwords, and connection strings MUST be read from environment variables
  or a secrets manager.
- Local `.env` files MUST be git-ignored; a `.env.example` with placeholder values MAY be
  committed.
- Any secret accidentally committed MUST be treated as leaked and rotated.

Rationale: committed secrets are effectively public and cannot be reliably removed.

### V. Simplicity

The simplest solution that meets the requirement MUST be chosen.

- No speculative features, abstractions, or configuration (YAGNI).
- New dependencies MUST be justified by a concrete need the standard library or existing
  dependencies cannot meet.
- Added complexity MUST be justified in the plan or pull request.

Rationale: simple code is easier to test, review, and change.

## Technical Constraints

- Language: Python, with full type hints (Principle II).
- Testing: pytest is the required test framework (Principle I).
- LLM integration: all structured LLM responses pass through schema validation (Principle III).
- Configuration and credentials come from the environment (Principle IV).

## Development Workflow & Quality Gates

A change MUST NOT be merged unless:

1. `pytest` passes with tests covering the change.
2. New or changed code is fully type-hinted.
3. Any new LLM call has a schema and validation tests.
4. No secrets are present in the diff.
5. Any added complexity or dependency is justified.

## Governance

This constitution supersedes other project practices. Where they conflict, this document wins.

- Amendments MUST be made by editing this file with a stated rationale and an updated version.
- Versioning follows semantic versioning: MAJOR for removing or redefining a principle, MINOR
  for adding a principle or materially expanding guidance, PATCH for clarifications and wording.
- Every plan and review MUST check compliance with the Core Principles; deviations MUST be
  justified in writing.

**Version**: 1.0.0 | **Ratified**: 2026-10-30 | **Last Amended**: 2026-10-30
