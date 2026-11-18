"""Offline configuration tests using only synthetic environment values."""

import os
from pathlib import Path
from types import MappingProxyType

import pytest
from pydantic import ValidationError

import expense_approval.settings as settings_module
from expense_approval.settings import Settings, load_settings


def test_defaults_and_missing_optional_key() -> None:
    settings = load_settings({})

    assert settings.jev_min_confidence == 0.70
    assert settings.jev_min_probability_margin == 0.30
    assert settings.openrouter_api_key is None


def test_valid_overrides_and_optional_key() -> None:
    settings = load_settings(
        {
            "OPENROUTER_API_KEY": "offline-example-key",
            "JEV_MIN_CONFIDENCE": "0.85",
            "JEV_MIN_PROBABILITY_MARGIN": "0.20",
        }
    )

    assert settings.jev_min_confidence == 0.85
    assert settings.jev_min_probability_margin == 0.20
    assert settings.openrouter_api_key is not None
    assert settings.openrouter_api_key.get_secret_value() == "offline-example-key"


@pytest.mark.parametrize(
    "environment_name", ["JEV_MIN_CONFIDENCE", "JEV_MIN_PROBABILITY_MARGIN"]
)
@pytest.mark.parametrize("boundary", ["0", "1"])
def test_threshold_boundaries(environment_name: str, boundary: str) -> None:
    settings = load_settings({environment_name: boundary})

    if environment_name == "JEV_MIN_CONFIDENCE":
        assert settings.jev_min_confidence == float(boundary)
        assert settings.jev_min_probability_margin == 0.30
    else:
        assert settings.jev_min_probability_margin == float(boundary)
        assert settings.jev_min_confidence == 0.70


@pytest.mark.parametrize(
    ("environment_name", "field_name"),
    [
        ("JEV_MIN_CONFIDENCE", "jev_min_confidence"),
        ("JEV_MIN_PROBABILITY_MARGIN", "jev_min_probability_margin"),
    ],
)
@pytest.mark.parametrize(
    "invalid_value",
    ["", " \t\n", "not-a-number", "-0.01", "1.01", "NaN", "inf", "-inf"],
)
def test_invalid_thresholds_do_not_fall_back_to_defaults(
    environment_name: str, field_name: str, invalid_value: str
) -> None:
    with pytest.raises(ValidationError) as captured_error:
        load_settings({environment_name: invalid_value})

    assert captured_error.value.errors()[0]["loc"] == (field_name,)


def test_both_invalid_thresholds_are_reported() -> None:
    with pytest.raises(ValidationError) as captured_error:
        load_settings({"JEV_MIN_CONFIDENCE": "", "JEV_MIN_PROBABILITY_MARGIN": "2"})

    assert {error["loc"] for error in captured_error.value.errors()} == {
        ("jev_min_confidence",),
        ("jev_min_probability_margin",),
    }


def test_secret_is_redacted_in_representations_and_serialization() -> None:
    secret_value = "synthetic-secret-that-must-not-be-displayed"
    settings = load_settings({"OPENROUTER_API_KEY": secret_value})

    for representation in (
        repr(settings),
        str(settings),
        repr(settings.openrouter_api_key),
        str(settings.openrouter_api_key),
        repr(settings.model_dump()),
        settings.model_dump_json(),
    ):
        assert secret_value not in representation

    assert settings.model_dump(mode="json")["openrouter_api_key"] == "**********"


def test_secret_is_absent_from_threshold_validation_errors() -> None:
    secret_value = "synthetic-secret-that-must-not-appear-in-errors"
    with pytest.raises(ValidationError) as captured_error:
        load_settings(
            {"OPENROUTER_API_KEY": secret_value, "JEV_MIN_CONFIDENCE": "invalid"}
        )

    for representation in (
        str(captured_error.value),
        repr(captured_error.value),
        repr(captured_error.value.errors()),
        captured_error.value.json(),
    ):
        assert secret_value not in representation


def test_supplied_environment_is_not_mutated() -> None:
    environment = {"JEV_MIN_CONFIDENCE": "0.9", "UNRELATED_VARIABLE": "ignored"}
    original_environment = environment.copy()

    settings = load_settings(MappingProxyType(environment))

    assert environment == original_environment
    assert settings.jev_min_confidence == 0.9


def test_process_environment_is_used_only_when_supplied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_environment = {"JEV_MIN_CONFIDENCE": "0.8"}
    monkeypatch.setattr(os, "environ", process_environment)

    assert load_settings({}).jev_min_confidence == 0.70
    assert load_settings(os.environ).jev_min_confidence == 0.8
    assert process_environment == {"JEV_MIN_CONFIDENCE": "0.8"}


def test_module_does_not_create_settings_instance() -> None:
    assert not any(
        isinstance(value, Settings) for value in vars(settings_module).values()
    )


def test_settings_cannot_be_modified() -> None:
    settings = load_settings({})

    with pytest.raises(ValidationError) as captured_error:
        settings.jev_min_confidence = 0.9

    assert captured_error.value.errors()[0]["type"] == "frozen_instance"
    assert settings.jev_min_confidence == 0.70


def test_dotenv_file_is_not_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text(
        "JEV_MIN_CONFIDENCE=invalid\nOPENROUTER_API_KEY=synthetic-file-key\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    settings = load_settings({})

    assert settings.jev_min_confidence == 0.70
    assert settings.openrouter_api_key is None


def test_only_three_configuration_variables_are_supported() -> None:
    assert set(Settings.model_fields) == {
        "openrouter_api_key",
        "jev_min_confidence",
        "jev_min_probability_margin",
    }
    assert load_settings({"UNRELATED_VARIABLE": "ignored"}) == load_settings({})
