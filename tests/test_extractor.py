import json
from types import SimpleNamespace
from typing import cast

import httpx2
import pytest
from openai import APIConnectionError, OpenAI

from meeting_actions.config import Settings
from meeting_actions.extractor import SYSTEM_PROMPT, ExtractionError, OpenAICompatibleExtractor
from meeting_actions.models import ActionItem, ExtractionResult

NOTES = "Alice will send the budget report by Friday."


def make_response(
    content: str | None, finish_reason: str = "stop", refusal: str | None = None
) -> SimpleNamespace:
    message = SimpleNamespace(content=content, refusal=refusal)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


class StubCompletions:
    def __init__(self, response: SimpleNamespace | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace | None:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


class StubClient:
    def __init__(self, completions: StubCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


def make_extractor(
    response: SimpleNamespace | None = None, error: Exception | None = None
) -> tuple[OpenAICompatibleExtractor, StubCompletions]:
    completions = StubCompletions(response, error)
    extractor = OpenAICompatibleExtractor(cast(OpenAI, StubClient(completions)), "test-model")
    return extractor, completions


def test_valid_reply_returns_items() -> None:
    reply = json.dumps(
        {"action_items": [{"task": "send the budget report", "owner": "Alice", "due_date": "Friday"}]}
    )
    extractor, _ = make_extractor(make_response(reply))

    assert extractor.extract(NOTES) == [
        ActionItem(task="send the budget report", owner="Alice", due_date="Friday")
    ]


def test_empty_reply_returns_empty_list() -> None:
    extractor, _ = make_extractor(make_response('{"action_items": []}'))

    assert extractor.extract("We reviewed Q3 numbers. Revenue was flat.") == []


def test_prompt_forbids_invented_items_and_allows_empty_list() -> None:
    assert "do not invent items" in SYSTEM_PROMPT
    assert '{"action_items": []}' in SYSTEM_PROMPT


def test_request_shape() -> None:
    extractor, completions = make_extractor(make_response('{"action_items": []}'))
    extractor.extract(NOTES)

    kwargs = completions.kwargs
    assert kwargs["model"] == "test-model"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs

    messages = cast(list[dict[str, str]], kwargs["messages"])
    assert [m["role"] for m in messages] == ["system", "user"]
    assert json.dumps(ExtractionResult.model_json_schema()) in messages[0]["content"]
    assert NOTES in messages[1]["content"]


@pytest.mark.parametrize(
    "response",
    [
        make_response('{"action_items": []}', finish_reason="length"),
        make_response(None),
        make_response("", refusal="I can't help with that."),
        make_response("Sure! Here are the items: ..."),
        make_response('{"action_items": [{"task": "x"}]}'),
    ],
    ids=["cut-off", "no-content", "refusal", "not-json", "schema-mismatch"],
)
def test_bad_replies_raise(response: SimpleNamespace) -> None:
    extractor, _ = make_extractor(response)

    with pytest.raises(ExtractionError):
        extractor.extract(NOTES)


def test_api_error_raises() -> None:
    error = APIConnectionError(request=httpx2.Request("POST", "https://test"))
    extractor, _ = make_extractor(error=error)

    with pytest.raises(ExtractionError):
        extractor.extract(NOTES)


def test_error_message_does_not_contain_notes() -> None:
    extractor, _ = make_extractor(make_response("not json"))

    with pytest.raises(ExtractionError) as exc_info:
        extractor.extract(NOTES)
    assert "budget report" not in str(exc_info.value)


def test_from_settings_builds_client_without_network() -> None:
    extractor = OpenAICompatibleExtractor.from_settings(
        Settings(base_url="https://test/v1", api_key="test-key", model="m")
    )

    assert extractor.model == "m"
    assert str(extractor.client.base_url).startswith("https://test/v1")
    assert extractor.client.timeout == 15.0
    assert extractor.client.max_retries == 1
