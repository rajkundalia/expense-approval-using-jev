"""Raw-value capture and one direct-SQL storage round trip; no claim workflows."""

import copy
import json
import struct
import sys
from datetime import date, datetime
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from expense_approval.database import (
    connect_database,
    initialize_database,
    write_transaction,
)
from expense_approval.evidence import encode_raw_evidence


def captured_value(value: object) -> dict[str, object]:
    envelope = json.loads(encode_raw_evidence(value))
    assert envelope["format"] == "raw-evidence"
    assert envelope["version"] == 1
    return envelope["value"]


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, {"type": "null", "value": None}),
        (True, {"type": "bool", "value": True}),
        (False, {"type": "bool", "value": False}),
        ("  Straße\t\n", {"type": "str", "value": "  Straße\t\n"}),
        ("12.340", {"type": "str", "value": "12.340"}),
        (0, {"type": "int", "value": "0"}),
        (-12, {"type": "int", "value": "-12"}),
        (date(2024, 2, 29), {"type": "date", "value": "2024-02-29"}),
        ([], {"type": "list", "items": []}),
        ({}, {"type": "dict", "entries": []}),
    ],
)
def test_supported_values_have_distinct_tags(
    value: object, expected: dict[str, object]
) -> None:
    assert captured_value(value) == expected


def test_exceptionally_large_integers_are_exact_without_global_changes() -> None:
    digit_limit = sys.get_int_max_str_digits()
    huge = 10 ** max(5000, digit_limit + 1) + 1
    digits = "1" + "0" * (max(5000, digit_limit + 1) - 1) + "1"

    with localcontext() as context:
        context.prec = 2
        assert captured_value(huge) == {"type": "int", "value": digits}
        assert captured_value(-huge) == {"type": "int", "value": "-" + digits}
    assert sys.get_int_max_str_digits() == digit_limit


@pytest.mark.parametrize(
    "text",
    [
        "12.340",
        "12.0000",
        "-0.000",
        "1E+1000",
        "123456789012345678901234567890.1201",
        "Infinity",
        "-Infinity",
        "NaN",
        "-NaN123",
        "sNaN456",
    ],
)
def test_decimal_sign_digits_and_exponent_are_preserved(text: str) -> None:
    value = Decimal(text)
    parts = value.as_tuple()
    with localcontext() as context:
        context.prec = 2
        node = captured_value(value)
    assert node == {
        "type": "decimal",
        "sign": parts.sign,
        "digits": list(parts.digits),
        "exponent": parts.exponent,
    }
    assert (
        Decimal((node["sign"], tuple(node["digits"]), node["exponent"])).as_tuple()
        == parts
    )


@pytest.mark.parametrize("value", [0.0, -0.0, 0.1, 12.345, 5e-324, sys.float_info.max])
def test_finite_floats_are_exact(value: float) -> None:
    node = captured_value(value)
    assert node["type"] == "float"
    assert struct.pack("!d", float.fromhex(node["value"])) == struct.pack("!d", value)


@pytest.mark.parametrize(
    "value,marker", [(float("inf"), "infinity"), (float("-inf"), "-infinity")]
)
def test_infinite_floats_have_explicit_markers(value: float, marker: str) -> None:
    assert captured_value(value) == {"type": "float", "value": marker}


@pytest.mark.parametrize("bits", ["7ff8000000000001", "fff8000000000002"])
def test_nan_marker_preserves_sign_and_payload(bits: str) -> None:
    value = struct.unpack("!d", bytes.fromhex(bits))[0]
    assert captured_value(value) == {"type": "float", "value": "nan", "bits": bits}


def test_dictionary_order_list_order_and_field_presence_are_preserved() -> None:
    value = {"z": [False, "12.340", 12], "type": "decimal", "entries": None}
    original = copy.deepcopy(value)
    snapshot = encode_raw_evidence(value)
    node = json.loads(snapshot)["value"]
    assert node == {
        "type": "dict",
        "entries": [
            [
                "z",
                {
                    "type": "list",
                    "items": [
                        {"type": "bool", "value": False},
                        {"type": "str", "value": "12.340"},
                        {"type": "int", "value": "12"},
                    ],
                },
            ],
            ["type", {"type": "str", "value": "decimal"}],
            ["entries", {"type": "null", "value": None}],
        ],
    }
    assert value == original
    value["z"].append("later mutation")
    assert json.loads(snapshot)["value"] == node
    assert captured_value({}) != captured_value({"invoice_line_number": 1})


def test_direct_python_values_do_not_modify_original_evidence() -> None:
    value = {
        "amount": Decimal("12.340"),
        "invoice_date": date(2024, 2, 29),
        "text": " X\t ",
    }
    snapshot = captured_value(value)
    assert value["amount"].as_tuple() == Decimal("12.340").as_tuple()
    assert value["invoice_date"] == date(2024, 2, 29)
    assert value["text"] == " X\t "
    assert [entry[1]["type"] for entry in snapshot["entries"]] == [
        "decimal",
        "date",
        "str",
    ]


@pytest.mark.parametrize("value", [b"bytes", ("tuple",), {1}, datetime(2026, 10, 31)])
def test_unsupported_types_are_explicitly_incomplete(value: object) -> None:
    node = captured_value(value)
    assert node["type"] == "incomplete"
    assert node["reason"] == "unsupported_type"
    assert (
        node["python_type"] == type(value).__module__ + "." + type(value).__qualname__
    )


def test_arbitrary_hooks_and_subclass_methods_are_not_called() -> None:
    class Hostile:
        def __str__(self) -> str:
            raise AssertionError("str must not run")

        def __repr__(self) -> str:
            raise AssertionError("repr must not run")

        def to_json(self) -> str:
            raise AssertionError("custom serialization must not run")

    class HostileList(list):
        def __iter__(self):
            raise AssertionError("subclass iteration must not run")

    class HostileDate(date):
        def isoformat(self) -> str:
            raise AssertionError("subclass date formatting must not run")

    for value in (Hostile(), HostileList(), HostileDate(2026, 10, 31)):
        assert captured_value(value)["reason"] == "unsupported_type"
    entries = captured_value({Hostile(): "kept"})["entries"]
    assert entries[0][0]["reason"] == "non_string_key"
    assert entries[0][1] == {"type": "str", "value": "kept"}


def test_non_string_keys_are_described_without_losing_surrounding_values() -> None:
    value = {"before": "kept", 12: ["invalid key"], "after": True}
    entries = captured_value(value)["entries"]
    assert entries == [
        ["before", {"type": "str", "value": "kept"}],
        [
            {
                "type": "incomplete",
                "reason": "non_string_key",
                "python_type": "builtins.int",
            },
            {"type": "list", "items": [{"type": "str", "value": "invalid key"}]},
        ],
        ["after", {"type": "bool", "value": True}],
    ]
    assert list(value) == ["before", 12, "after"]


@pytest.mark.parametrize("container_type", [list, dict])
def test_cycles_are_incomplete_without_mutating_input(container_type: type) -> None:
    value = container_type()
    if container_type is list:
        value.append(value)
        child = captured_value(value)["items"][0]
        assert value[0] is value
    else:
        value["self"] = value
        child = captured_value(value)["entries"][0][1]
        assert value["self"] is value
    assert child == {
        "type": "incomplete",
        "reason": "cyclic_reference",
        "python_type": "builtins." + container_type.__name__,
    }


def test_shared_noncyclic_containers_are_captured_each_time() -> None:
    shared = {"amount": ["12.340"]}
    node = captured_value([shared, shared])
    assert node["items"] == [captured_value(shared), captured_value(shared)]
    assert node["items"][0]["type"] == "dict"


def test_unexpected_failure_propagates_without_mutating_input() -> None:
    value: list[object] = []
    current = value
    depth = sys.getrecursionlimit() + 5
    for _ in range(depth):
        child: list[object] = []
        current.append(child)
        current = child
    with pytest.raises(RecursionError):
        encode_raw_evidence(value)
    current = value
    for _ in range(depth):
        assert len(current) == 1
        current = current[0]
    assert current == []


def test_json_is_strict_and_strings_are_not_normalized() -> None:
    snapshot = encode_raw_evidence(
        [float("nan"), float("inf"), "\ud800\x00 Café\u00a0"]
    )

    def reject_bare_constant(text: str) -> None:
        pytest.fail("Nonstandard JSON constant: " + text)

    node = json.loads(snapshot, parse_constant=reject_bare_constant)["value"]
    assert node["items"][2] == {"type": "str", "value": "\ud800\x00 Café\u00a0"}
    snapshot.encode("utf-8")


def test_encoded_accepted_and_invalid_evidence_round_trips_through_sqlite(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.sqlite3"
    initialize_database(path)
    original = {
        "employee_id": "EMP-1",
        "merchant_name": "  Example MERCHANT  ",
        "invoice_number": "INV-1",
        "invoice_date": "2026-10-31",
        "invoice_item_name": "Running shoes",
        "invoice_item_amount": "12.340",
        "reimbursement_category": "WELLNESS",
        "requested_reimbursement": "12.00",
        "employee_justification": "For daily running",
    }
    accepted = encode_raw_evidence(original)
    failed = encode_raw_evidence(
        {**original, "invoice_item_amount": [True, "not money"]}
    )
    with connect_database(path) as connection:
        with write_transaction(connection):
            connection.execute("""INSERT INTO claims (
                claim_id, submitted_at, original_submission_date, current_evidence_version,
                state_version, normalized_employee_id, normalized_merchant_name,
                normalized_invoice_number, invoice_line_number
            ) VALUES ('claim-1', '2026-10-31T12:00:00+00:00', '2026-10-31',
                      1, 1, 'emp-1', 'example merchant', 'inv-1', '1')""")
            connection.execute(
                """INSERT INTO claim_revisions (
                revision_id, claim_id, evidence_version, submitted_at, action_kind,
                disposition, raw_evidence_json, invoice_date, reimbursement_category,
                invoice_item_amount, requested_reimbursement, validation_details_json
            ) VALUES ('accepted', 'claim-1', 1, '2026-10-31T12:00:00+00:00', 'INITIAL',
                      'ACCEPTED', ?, '2026-10-31', 'WELLNESS', '12.340', '12.00', '{}')""",
                (accepted,),
            )
            connection.execute(
                """INSERT INTO claim_revisions (
                revision_id, claim_id, submitted_at, action_kind, disposition,
                raw_evidence_json, validation_details_json
            ) VALUES ('failed', 'claim-1', '2026-11-01T12:00:00+00:00', 'CORRECTION',
                      'INVALID', ?, '{"field":"invoice_item_amount"}')""",
                (failed,),
            )
    with connect_database(path) as connection:
        assert connection.execute("""SELECT revision_id, evidence_version, raw_evidence_json
            FROM claim_revisions ORDER BY revision_id""").fetchall() == [
            ("accepted", 1, accepted),
            ("failed", None, failed),
        ]
        assert connection.execute(
            "SELECT current_evidence_version FROM claims"
        ).fetchone() == (1,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
