import logging
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from conftest import FakeExtractor
from meeting_actions.extractor import ExtractionError
from meeting_actions.models import ActionItem

MakeClient = Callable[[FakeExtractor], TestClient]

URL = "/v1/action-items"


def test_returns_items_in_order(make_client: MakeClient) -> None:
    fake = FakeExtractor(
        items=[
            ActionItem(task="send the budget report", owner="Alice", due_date="Friday"),
            ActionItem(task="book the venue", owner="Bob", due_date="next Tuesday"),
        ]
    )
    response = make_client(fake).post(URL, json={"notes": "Alice ... Bob ..."})

    assert response.status_code == 200
    assert response.json() == {
        "action_items": [
            {"task": "send the budget report", "owner": "Alice", "due_date": "Friday"},
            {"task": "book the venue", "owner": "Bob", "due_date": "next Tuesday"},
        ]
    }


def test_missing_owner_and_due_date_are_null(make_client: MakeClient) -> None:
    fake = FakeExtractor(items=[ActionItem(task="update the wiki", owner=None, due_date=None)])
    response = make_client(fake).post(URL, json={"notes": "Someone should update the wiki."})

    assert response.status_code == 200
    assert response.json() == {
        "action_items": [{"task": "update the wiki", "owner": None, "due_date": None}]
    }


def test_extractor_receives_trimmed_notes(make_client: MakeClient) -> None:
    fake = FakeExtractor()
    make_client(fake).post(URL, json={"notes": "  \n Alice will call Bob. \t "})

    assert fake.calls == ["Alice will call Bob."]


def test_extraction_failure_returns_502(make_client: MakeClient) -> None:
    fake = FakeExtractor(error=ExtractionError("bad reply"))
    response = make_client(fake).post(URL, json={"notes": "Alice will call Bob."})

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "extraction_failed",
            "message": "Could not extract action items. Please try again.",
        }
    }


@pytest.mark.parametrize("error", [None, ExtractionError("bad reply")])
def test_notes_never_logged(
    make_client: MakeClient, caplog: pytest.LogCaptureFixture, error: Exception | None
) -> None:
    secret_notes = "Confidential: Carol will draft the merger memo by Monday."
    fake = FakeExtractor(error=error)
    caplog.set_level(logging.DEBUG)

    make_client(fake).post(URL, json={"notes": secret_notes})

    assert any(r.name.startswith("meeting_actions") for r in caplog.records)
    assert "merger memo" not in caplog.text
    assert "Carol" not in caplog.text


def test_no_action_items_returns_empty_list(make_client: MakeClient) -> None:
    fake = FakeExtractor(items=[])
    response = make_client(fake).post(
        URL, json={"notes": "We reviewed Q3 numbers. Revenue was flat."}
    )

    assert response.status_code == 200
    assert response.json() == {"action_items": []}


EMPTY_ERROR = {"error": {"code": "empty_notes", "message": "Notes must not be empty."}}
INVALID_ERROR = {
    "error": {
        "code": "invalid_request",
        "message": "Request body must be JSON with a 'notes' string field.",
    }
}


@pytest.mark.parametrize("notes", ["", "  \n\t "])
def test_empty_notes_rejected(make_client: MakeClient, notes: str) -> None:
    fake = FakeExtractor()
    response = make_client(fake).post(URL, json={"notes": notes})

    assert response.status_code == 400
    assert response.json() == EMPTY_ERROR
    assert fake.calls == []


@pytest.mark.parametrize("notes", ["a" * 20_000, " " + "a" * 20_000 + " "])
def test_notes_at_limit_accepted(make_client: MakeClient, notes: str) -> None:
    fake = FakeExtractor()
    response = make_client(fake).post(URL, json={"notes": notes})

    assert response.status_code == 200
    assert len(fake.calls) == 1


def test_notes_over_limit_rejected(make_client: MakeClient) -> None:
    fake = FakeExtractor()
    response = make_client(fake).post(URL, json={"notes": "a" * 20_001})

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "notes_too_long",
            "message": "Notes must be at most 20,000 characters; received 20,001.",
        }
    }
    assert fake.calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"json": {"text": "hi"}},
        {"json": {"notes": 123}},
        {"content": "not json", "headers": {"Content-Type": "application/json"}},
    ],
    ids=["wrong-field", "not-a-string", "not-json"],
)
def test_malformed_request_rejected(make_client: MakeClient, kwargs: dict[str, object]) -> None:
    fake = FakeExtractor()
    response = make_client(fake).post(URL, **kwargs)  # type: ignore[arg-type]

    assert response.status_code == 400
    assert response.json() == INVALID_ERROR
    assert fake.calls == []


@pytest.mark.parametrize(
    ("payload", "error", "outcome"),
    [
        ({"notes": "Dana will order laptops."}, None, "ok"),
        ({"notes": "Dana will order laptops."}, ExtractionError("x"), "extraction_failed"),
        ({"notes": "   "}, None, "empty_notes"),
        ({"notes": "Dana will order laptops." * 1_000}, None, "notes_too_long"),
        ({"text": "Dana will order laptops."}, None, "invalid_request"),
    ],
    ids=["ok", "extraction_failed", "empty_notes", "notes_too_long", "invalid_request"],
)
def test_every_outcome_is_logged_once(
    make_client: MakeClient,
    caplog: pytest.LogCaptureFixture,
    payload: dict[str, str],
    error: Exception | None,
    outcome: str,
) -> None:
    caplog.set_level(logging.INFO, logger="meeting_actions")

    make_client(FakeExtractor(error=error)).post(URL, json=payload)

    lines = [r.getMessage() for r in caplog.records if r.name == "meeting_actions"]
    assert len(lines) == 1
    assert f"outcome={outcome} " in lines[0] + " "
    assert "laptops" not in caplog.text


def test_health(make_client: MakeClient) -> None:
    response = make_client(FakeExtractor()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
