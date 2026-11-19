"""Pure identity-text normalization, separate from structural validation."""


def normalize_identity_text(value: str) -> str:
    """Collapse whitespace and case-fold text without changing original evidence.

    Punctuation is preserved. Blank strings may normalize to an empty string;
    callers retain responsibility for structural validation and persistence.
    """
    if not isinstance(value, str):
        raise TypeError("Identity text must be a string.")
    return " ".join(value.split()).casefold()
