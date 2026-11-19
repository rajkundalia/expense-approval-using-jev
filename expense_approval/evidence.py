"""Versioned raw-value capture, without claim validation or persistence."""

import json
import math
import struct
from datetime import date
from decimal import Decimal


def encode_raw_evidence(value: object) -> str:
    """Capture supported values in a version-1, type-tagged JSON envelope.

    Support exact built-in null/bool/str/int/float/list/dict types, Decimal and
    plain date. Preserve ordering and field presence without applying defaults.
    Unsupported values, non-string keys and cycles receive incomplete-capture
    descriptors; no arbitrary stringification or serialization hooks are used.
    Subclasses and datetime are unsupported, rather than coerced to base types.

    Callers supply stable input during capture. This function does not mutate it.
    Unexpected errors propagate; no partial JSON is returned. The format captures
    values, not original HTTP bytes, object identity or arbitrary Python objects.
    """
    envelope = {
        "format": "raw-evidence",
        "version": 1,
        "value": _encode_value(value, set()),
    }
    return json.dumps(
        envelope, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )


def _incomplete(value: object, reason: str) -> dict[str, object]:
    value_type = type(value)
    return {
        "type": "incomplete",
        "reason": reason,
        "python_type": (
            type.__getattribute__(value_type, "__module__")
            + "."
            + type.__getattribute__(value_type, "__qualname__")
        ),
    }


def _encode_value(value: object, active_containers: set[int]) -> dict[str, object]:
    value_type = type(value)
    if value is None:
        return {"type": "null", "value": None}
    if value_type is bool:
        return {"type": "bool", "value": value}
    if value_type is str:
        return {"type": "str", "value": value}
    if value_type is int:
        # Decimal(int) is exact and bypasses the integer-to-string digit limit.
        return {"type": "int", "value": str(Decimal(value))}
    if value_type is float:
        if math.isfinite(value):
            return {"type": "float", "value": value.hex()}
        if math.isnan(value):
            # The marker identifies NaN; bits retain its sign and payload.
            return {
                "type": "float",
                "value": "nan",
                "bits": struct.pack("!d", value).hex(),
            }
        return {"type": "float", "value": "-infinity" if value < 0 else "infinity"}
    if value_type is Decimal:
        parts = value.as_tuple()
        return {
            "type": "decimal",
            "sign": parts.sign,
            "digits": list(parts.digits),
            "exponent": parts.exponent,
        }
    if value_type is date:
        return {"type": "date", "value": value.isoformat()}
    if value_type is not list and value_type is not dict:
        return _incomplete(value, "unsupported_type")

    container_id = id(value)
    if container_id in active_containers:
        return _incomplete(value, "cyclic_reference")
    active_containers.add(container_id)
    try:
        if value_type is list:
            return {
                "type": "list",
                "items": [_encode_value(item, active_containers) for item in value],
            }
        return {
            "type": "dict",
            "entries": [
                [
                    key if type(key) is str else _incomplete(key, "non_string_key"),
                    _encode_value(item, active_containers),
                ]
                for key, item in value.items()
            ],
        }
    finally:
        active_containers.remove(container_id)
