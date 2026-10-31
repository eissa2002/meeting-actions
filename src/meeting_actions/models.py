from pydantic import BaseModel, field_validator

MAX_NOTES_CHARS = 20_000


class ActionItem(BaseModel):
    """One commitment found in the notes. Missing owner or due date is null, never guessed."""

    task: str
    owner: str | None
    due_date: str | None

    @field_validator("task")
    @classmethod
    def task_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("task must not be empty")
        return value


class ExtractionResult(BaseModel):
    """Schema the LLM reply must match."""

    action_items: list[ActionItem]


class ExtractRequest(BaseModel):
    # Length is checked in the route so the error messages match the spec.
    notes: str


class ExtractResponse(BaseModel):
    action_items: list[ActionItem]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
