import pytest

from meeting_actions.config import ConfigError, Settings, load_settings

FULL_ENV = {
    "LLM_BASE_URL": "https://test/v1",
    "LLM_API_KEY": "test-key",
    "LLM_MODEL": "test-model",
}


def test_loads_all_values() -> None:
    assert load_settings(FULL_ENV) == Settings(
        base_url="https://test/v1", api_key="test-key", model="test-model"
    )


@pytest.mark.parametrize("missing", ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"])
def test_missing_variable_is_named(missing: str) -> None:
    env = {k: v for k, v in FULL_ENV.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        load_settings(env)


def test_empty_string_counts_as_missing() -> None:
    with pytest.raises(ConfigError, match="LLM_API_KEY"):
        load_settings({**FULL_ENV, "LLM_API_KEY": ""})


def test_all_missing_variables_are_listed() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_settings({})
    message = str(exc_info.value)
    for name in FULL_ENV:
        assert name in message
