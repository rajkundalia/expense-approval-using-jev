"""Identity-text behavior without persistence or reimbursement validation."""

import pytest

from expense_approval.identity import normalize_identity_text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" EMP-001 ", "emp-001"),
        ("  Example \t MERCHANT\nLtd. ", "example merchant ltd."),
        ("Straße", "strasse"),
        ("ΟΣ ος οσ", "οσ οσ οσ"),
        ("  Café\u00a0\u2003STORE\u202f ", "café store"),
        ("INV/A-001_02.#", "inv/a-001_02.#"),
        ("", ""),
        (" ", ""),
        ("\t\r\n", ""),
        ("\u00a0\u2003\u202f", ""),
    ],
)
def test_normalization_and_idempotence(value: str, expected: str) -> None:
    normalized = normalize_identity_text(value)

    assert normalized == expected
    assert normalize_identity_text(normalized) == normalized


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("INV/001", "INV-001"),
        ("Acme & Co.", "Acme Co."),
        ("INV 001", "INV001"),
    ],
)
def test_meaningful_distinctions_are_preserved(first: str, second: str) -> None:
    assert normalize_identity_text(first) != normalize_identity_text(second)


@pytest.mark.parametrize("value", [None, 1, 1.0, True, b"EMP", ["EMP"], {"id": "EMP"}])
def test_non_string_inputs_raise_type_error(value: object) -> None:
    with pytest.raises(TypeError, match="Identity text must be a string"):
        normalize_identity_text(value)


def test_original_text_is_preserved() -> None:
    original = "\t Example\u00a0 MERCHANT & Co.\n"

    normalized = normalize_identity_text(original)

    assert original == "\t Example\u00a0 MERCHANT & Co.\n"
    assert normalized == "example merchant & co."
