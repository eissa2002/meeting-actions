import json
from typing import Protocol

from openai import APIError, OpenAI
from pydantic import ValidationError

from meeting_actions.config import Settings
from meeting_actions.models import ActionItem, ExtractionResult

SYSTEM_PROMPT = f"""You extract action items from meeting notes.

Return only a JSON object that matches this JSON schema:
{json.dumps(ExtractionResult.model_json_schema())}

Rules:
- List action items in the order they appear in the notes.
- If a task is assigned to several people, create one item per owner.
- Copy owner names and due dates exactly as written in the notes; do not convert dates.
- Use null for the owner or due_date when the notes do not state it.
- Only include tasks someone committed to or was assigned in the notes; do not invent items.
  If there are none, return {{"action_items": []}}."""


class ExtractionError(Exception):
    """The LLM call failed or its reply did not match the schema."""


class Extractor(Protocol):
    def extract(self, notes: str) -> list[ActionItem]: ...


class OpenAICompatibleExtractor:
    """Calls any OpenAI-compatible Chat Completions API and validates the reply."""

    def __init__(self, client: OpenAI, model: str) -> None:
        self.client = client
        self.model = model

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAICompatibleExtractor":
        client = OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=15.0,
            max_retries=1,
        )
        return cls(client, settings.model)

    def extract(self, notes: str) -> list[ActionItem]:
        # Error messages never include the notes (FR-012).
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": notes},
                ],
                response_format={"type": "json_object"},
            )
        except APIError as exc:
            raise ExtractionError(f"LLM request failed: {type(exc).__name__}") from exc

        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ExtractionError("LLM reply was cut off")
        if choice.message.refusal:
            raise ExtractionError("LLM refused the request")
        content = choice.message.content
        if not content:
            raise ExtractionError("LLM reply was empty")

        try:
            result = ExtractionResult.model_validate_json(content)
        except ValidationError as exc:
            raise ExtractionError("LLM reply did not match the schema") from exc
        return result.action_items
