import pytest
from pydantic import ValidationError

from meeting_actions.models import ActionItem, ExtractionResult


def test_accepts_empty_list() -> None:
    result = ExtractionResult.model_validate_json('{"action_items": []}')
    assert result.action_items == []


def test_accepts_items_with_strings_and_nulls() -> None:
    result = ExtractionResult.model_validate_json(
        '{"action_items": ['
        '{"task": "send the report", "owner": "Alice", "due_date": "Friday"},'
        '{"task": "book the venue", "owner": null, "due_date": null}'
        "]}"
    )
    assert result.action_items == [
        ActionItem(task="send the report", owner="Alice", due_date="Friday"),
        ActionItem(task="book the venue", owner=None, due_date=None),
    ]


def test_task_is_trimmed() -> None:
    item = ActionItem.model_validate_json(
        '{"task": "  send the report  ", "owner": null, "due_date": null}'
    )
    assert item.task == "send the report"


@pytest.mark.parametrize(
    "payload",
    [
        "{}",
        '{"action_items": [{"owner": "Alice", "due_date": null}]}',
        '{"action_items": [{"task": "", "owner": null, "due_date": null}]}',
        '{"action_items": [{"task": "   ", "owner": null, "due_date": null}]}',
        '{"action_items": [{"task": "x", "owner": 123, "due_date": null}]}',
        '{"action_items": [{"task": "x", "due_date": null}]}',
        "not json at all",
    ],
)
def test_rejects_invalid_output(payload: str) -> None:
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate_json(payload)
