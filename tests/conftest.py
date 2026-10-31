from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from meeting_actions.main import create_app
from meeting_actions.models import ActionItem


class FakeExtractor:
    """Stands in for the LLM: returns canned items or raises a canned error."""

    def __init__(
        self, items: list[ActionItem] | None = None, error: Exception | None = None
    ) -> None:
        self.items = items
        self.error = error
        self.calls: list[str] = []

    def extract(self, notes: str) -> list[ActionItem]:
        self.calls.append(notes)
        if self.error is not None:
            raise self.error
        return self.items or []


@pytest.fixture
def make_client() -> Callable[[FakeExtractor], TestClient]:
    def _make(fake: FakeExtractor) -> TestClient:
        return TestClient(create_app(extractor=fake))

    return _make
