"""Typed configuration loaded explicitly from a caller-supplied environment."""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Settings(BaseModel):
    """Local settings; Jev thresholds are provisional, not calibrated guarantees."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    openrouter_api_key: SecretStr | None = Field(default=None, repr=False)
    jev_min_confidence: float = Field(default=0.70, ge=0, le=1, allow_inf_nan=False)
    jev_min_probability_margin: float = Field(
        default=0.30, ge=0, le=1, allow_inf_nan=False
    )


def load_settings(environment: Mapping[str, str]) -> Settings:
    """Load only supported variables; callers explicitly pass os.environ if wanted.

    Missing thresholds use defaults; explicitly invalid values fail validation.
    The supplied mapping is the only data source; no files or network are accessed.
    """
    values: dict[str, str | SecretStr] = {}
    if "OPENROUTER_API_KEY" in environment:
        values["openrouter_api_key"] = SecretStr(environment["OPENROUTER_API_KEY"])

    for environment_name, field_name in (
        ("JEV_MIN_CONFIDENCE", "jev_min_confidence"),
        ("JEV_MIN_PROBABILITY_MARGIN", "jev_min_probability_margin"),
    ):
        if environment_name in environment:
            values[field_name] = environment[environment_name]

    return Settings.model_validate(values)
