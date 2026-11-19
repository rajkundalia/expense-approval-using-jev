"""Fixed-instant tests for the India business date."""

from datetime import date, datetime

import pytest

from expense_approval.clock import business_date


@pytest.mark.parametrize(
    ("instant_text", "expected"),
    [
        ("2026-10-31T12:00:00+00:00", date(2026, 10, 31)),
        ("2026-10-31T18:29:59.999999+00:00", date(2026, 10, 31)),
        ("2026-10-31T18:30:00+00:00", date(2026, 11, 1)),
        ("2026-10-31T23:00:00+00:00", date(2026, 11, 1)),
        ("2026-11-01T00:00:00+05:30", date(2026, 11, 1)),
        ("2026-10-31T11:30:00-07:00", date(2026, 11, 1)),
        ("2026-11-01T03:30:00+09:00", date(2026, 11, 1)),
    ],
)
def test_business_date_converts_aware_instants(
    instant_text: str, expected: date
) -> None:
    assert business_date(lambda: datetime.fromisoformat(instant_text)) == expected


def test_naive_time_source_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        business_date(lambda: datetime(2026, 10, 31, 18, 30))


@pytest.mark.parametrize("host_timezone", ["America/Los_Angeles", "Asia/Tokyo"])
def test_business_date_ignores_local_timezone_setting(
    monkeypatch: pytest.MonkeyPatch, host_timezone: str
) -> None:
    monkeypatch.setenv("TZ", host_timezone)
    instant = datetime.fromisoformat("2026-10-31T18:30:00+00:00")

    assert business_date(lambda: instant) == date(2026, 11, 1)


def test_submission_date_reads_time_source_once() -> None:
    instants = iter(
        [
            datetime.fromisoformat("2026-10-31T18:29:59+00:00"),
            datetime.fromisoformat("2026-10-31T18:30:00+00:00"),
        ]
    )

    assert business_date(lambda: next(instants)) == date(2026, 10, 31)
    assert next(instants) == datetime.fromisoformat("2026-10-31T18:30:00+00:00")
