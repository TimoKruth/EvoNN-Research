from __future__ import annotations

import datetime as dt
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

SCHEMA_VERSION = "evonn.test/v1"
GOLDEN_PATH = Path(__file__).parent / "golden" / "canonical-v1.json"


def _canonical() -> Any:
    return importlib.import_module("evonn_shared.canonical")


def _golden() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("value", "encoded"),
    [
        (None, '["evonn-canonical-json-v1","evonn.test/v1",["n"]]\n'),
        (False, '["evonn-canonical-json-v1","evonn.test/v1",["b",false]]\n'),
        (True, '["evonn-canonical-json-v1","evonn.test/v1",["b",true]]\n'),
        (-7, '["evonn-canonical-json-v1","evonn.test/v1",["i","-7"]]\n'),
        (0.0, '["evonn-canonical-json-v1","evonn.test/v1",["f","0x0.0p+0"]]\n'),
        (-0.0, '["evonn-canonical-json-v1","evonn.test/v1",["f","0x0.0p+0"]]\n'),
        (0.1, '["evonn-canonical-json-v1","evonn.test/v1",["f","0x1.999999999999ap-4"]]\n'),
        ("café", '["evonn-canonical-json-v1","evonn.test/v1",["s","café"]]\n'),
        (b"\xfb\xff", '["evonn-canonical-json-v1","evonn.test/v1",["y","-_8"]]\n'),
    ],
)
def test_canonical_bytes_tags_every_scalar(value: object, encoded: str) -> None:
    canonical = _canonical()

    assert canonical.canonical_bytes(value, schema_version=SCHEMA_VERSION) == encoded.encode()


def test_nested_sequences_maps_and_golden_sha_are_exact() -> None:
    canonical = _canonical()
    golden = _golden()["canonical"]
    value = {
        "é": "unicode",
        "z": ("tail",),
        "a": [
            None,
            False,
            True,
            -(2**63),
            2**63 - 1,
            -0.0,
            1.5,
            "café",
            b"\x00\xff\x10",
        ],
    }

    encoded = canonical.canonical_bytes(value, schema_version=SCHEMA_VERSION)

    assert encoded == golden["utf8"].encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == golden["sha256"]
    assert canonical.canonical_sha256(value, schema_version=SCHEMA_VERSION, digest_field=None) == golden["sha256"]


def test_mapping_keys_sort_by_normalized_utf8_bytes() -> None:
    canonical = _canonical()

    assert canonical.canonical_bytes(
        {"é": 3, "z": 2, "a": 1}, schema_version=SCHEMA_VERSION
    ) == (
        '["evonn-canonical-json-v1","evonn.test/v1",["m",'
        '[["a",["i","1"]],["z",["i","2"]],["é",["i","3"]]]]]\n'
    ).encode()


def test_nfc_equivalent_strings_have_identical_identity() -> None:
    canonical = _canonical()

    composed = canonical.canonical_bytes("café", schema_version=SCHEMA_VERSION)
    decomposed = canonical.canonical_bytes("café", schema_version=SCHEMA_VERSION)

    assert composed == decomposed


def test_nfc_mapping_key_collision_is_rejected_before_digest_omission() -> None:
    canonical = _canonical()
    value = {"digést": "first", "digést": "second"}

    with pytest.raises(canonical.NormalizedKeyCollisionError) as error:
        canonical.canonical_sha256(value, schema_version=SCHEMA_VERSION, digest_field="digést")

    assert error.value.code == "normalized_key_collision"
    assert str(error.value) == "mapping keys collide after NFC normalization: 'digést'"


@pytest.mark.parametrize("value", [-(2**63) - 1, 2**63])
def test_integers_outside_signed_64_bit_are_rejected(value: int) -> None:
    canonical = _canonical()

    with pytest.raises(canonical.IntegerOutOfRangeError) as error:
        canonical.canonical_bytes(value, schema_version=SCHEMA_VERSION)

    assert error.value.code == "integer_out_of_range"
    assert str(error.value) == "canonical integers must be in the signed 64-bit range"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_floats_are_rejected(value: float) -> None:
    canonical = _canonical()

    with pytest.raises(canonical.NonFiniteFloatError) as error:
        canonical.canonical_bytes(value, schema_version=SCHEMA_VERSION)

    assert error.value.code == "nonfinite_float"
    assert str(error.value) == "canonical floats must be finite binary64 values"


class AdversarialInt(int):
    def __str__(self) -> str:
        return "forged-int"


class AdversarialFloat(float):
    def hex(self) -> str:
        return "forged-float"


@pytest.mark.parametrize("value", [AdversarialInt(7), AdversarialFloat(1.5)])
def test_numeric_subclasses_with_overridden_formatters_are_rejected(value: object) -> None:
    canonical = _canonical()

    with pytest.raises(canonical.UnsupportedCanonicalTypeError) as error:
        canonical.canonical_bytes(value, schema_version=SCHEMA_VERSION)

    value_type = type(value)
    assert error.value.code == "unsupported_canonical_type"
    assert str(error.value) == (
        f"unsupported canonical value type: {value_type.__module__}.{value_type.__qualname__}"
    )


@pytest.mark.parametrize(
    "schema_version",
    [None, True, 1, "", "EVONN/v1", "has space", "é/v1", "-bad", "a" * 129],
)
def test_invalid_schema_versions_are_rejected(schema_version: object) -> None:
    canonical = _canonical()

    with pytest.raises(canonical.InvalidSchemaVersionError) as error:
        canonical.canonical_bytes(None, schema_version=schema_version)

    assert error.value.code == "invalid_schema_version"
    assert str(error.value) == (
        "schema_version must match ^[a-z0-9][a-z0-9._/-]{0,127}$"
    )


@pytest.mark.parametrize("schema_version", ["a", "1.0.0", "evonn.export.manifest/v1"])
def test_valid_schema_versions_are_bound_into_bytes(schema_version: str) -> None:
    canonical = _canonical()

    assert canonical.canonical_bytes(None, schema_version=schema_version).startswith(
        f'["evonn-canonical-json-v1","{schema_version}",'.encode()
    )


class CustomPathLike:
    def __fspath__(self) -> str:
        return "relative.txt"


@pytest.mark.parametrize(
    "value",
    [
        object(),
        {1, 2},
        bytearray(b"x"),
        memoryview(b"x"),
        Path("relative.txt"),
        CustomPathLike(),
        dt.date(2026, 1, 2),
        dt.time(3, 4, 5),
        dt.datetime(2026, 1, 2, 3, 4, 5),
    ],
)
def test_unsupported_pathlike_datetime_and_other_types_are_rejected(value: object) -> None:
    canonical = _canonical()

    with pytest.raises(canonical.UnsupportedCanonicalTypeError) as error:
        canonical.canonical_bytes(value, schema_version=SCHEMA_VERSION)

    assert error.value.code == "unsupported_canonical_type"
    assert str(error.value).startswith("unsupported canonical value type: ")


def test_mapping_keys_must_be_strings() -> None:
    canonical = _canonical()

    with pytest.raises(canonical.InvalidMappingKeyError) as error:
        canonical.canonical_bytes({1: "value"}, schema_version=SCHEMA_VERSION)

    assert error.value.code == "invalid_mapping_key"
    assert str(error.value) == "canonical mapping keys must be strings"


@pytest.mark.parametrize(
    "value",
    [
        {"timestamp": "2026-01-02T03:04:05Z"},
        {"event_timestamp": "2026-01-02T03:04:05Z"},
        {"created_at": "2026-01-02T03:04:05Z"},
        {"outer": [{"finished_at": None}]},
        {"outer": {"é_at": 1}},
    ],
)
def test_volatile_field_names_are_rejected_recursively(value: object) -> None:
    canonical = _canonical()

    with pytest.raises(canonical.VolatileFieldError) as error:
        canonical.canonical_bytes(value, schema_version=SCHEMA_VERSION)

    assert error.value.code == "volatile_field"
    assert str(error.value).startswith("volatile field is forbidden in canonical identity: ")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("path", "/tmp/result.json"),
        ("artifact_path", "C:\\results\\run.json"),
        ("artifact_path", "D:/results/run.json"),
        ("artifact_path", "C:drive-qualified.json"),
        ("output_path", "\\rooted\\result.json"),
        ("output_path", "\\\\server\\share\\run.json"),
        ("output_path", "//server/share/run.json"),
    ],
)
def test_absolute_or_drive_qualified_paths_are_rejected(key: str, value: str) -> None:
    canonical = _canonical()

    with pytest.raises(canonical.AbsolutePathError) as error:
        canonical.canonical_bytes({"outer": {key: value}}, schema_version=SCHEMA_VERSION)

    assert error.value.code == "absolute_path"
    assert str(error.value) == f"absolute or drive-qualified path is forbidden for field: {key!r}"


def test_unrelated_timestamp_looking_values_and_relative_paths_are_allowed() -> None:
    canonical = _canonical()
    value = {
        "note": "2026-01-02T03:04:05Z",
        "artifact_path": "../relative/results.json",
        "other_path": "nested/../results.json",
    }

    encoded = canonical.canonical_bytes(value, schema_version=SCHEMA_VERSION)

    assert b"2026-01-02T03:04:05Z" in encoded
    assert b"../relative/results.json" in encoded
    assert b"nested/../results.json" in encoded


def test_canonical_sha256_omits_only_the_normalized_top_level_digest_field() -> None:
    canonical = _canonical()
    golden = _golden()["digest_omission"]
    value = {"digest": "old", "nested": {"digest": "keep"}, "value": 1}

    assert canonical.canonical_sha256(value, schema_version=SCHEMA_VERSION) == golden["omitted_sha256"]
    assert (
        canonical.canonical_sha256(value, schema_version=SCHEMA_VERSION, digest_field=None)
        == golden["included_sha256"]
    )
    assert (
        canonical.canonical_sha256(
            {"digést": "old", "value": 1},
            schema_version=SCHEMA_VERSION,
            digest_field="digést",
        )
        == canonical.canonical_sha256({"value": 1}, schema_version=SCHEMA_VERSION)
    )


@pytest.mark.parametrize("digest_field", [True, 1, b"digest"])
def test_invalid_digest_fields_are_rejected(digest_field: object) -> None:
    canonical = _canonical()

    with pytest.raises(canonical.InvalidDigestFieldError) as error:
        canonical.canonical_sha256({}, schema_version=SCHEMA_VERSION, digest_field=digest_field)

    assert error.value.code == "invalid_digest_field"
    assert str(error.value) == "digest_field must be a string or None"


def test_digest_field_must_be_valid_utf8_after_normalization() -> None:
    canonical = _canonical()

    with pytest.raises(canonical.InvalidUnicodeError) as error:
        canonical.canonical_sha256(None, schema_version=SCHEMA_VERSION, digest_field=chr(0xD800))

    assert error.value.code == "invalid_unicode"
    assert str(error.value) == "digest_field must contain valid Unicode scalar values"


def test_raw_sha256_hashes_exact_bytes_and_has_a_distinct_domain() -> None:
    canonical = _canonical()
    golden = _golden()
    payload = bytes.fromhex(golden["raw_sha256"]["payload_hex"])

    assert canonical.sha256_bytes(payload) == golden["raw_sha256"]["sha256"]
    assert canonical.sha256_bytes(bytearray(payload)) == golden["raw_sha256"]["sha256"]
    assert canonical.sha256_bytes(memoryview(payload)) == golden["raw_sha256"]["sha256"]
    assert canonical.sha256_bytes(b"abc") != canonical.canonical_sha256(
        b"abc", schema_version=SCHEMA_VERSION, digest_field=None
    )
    assert canonical.canonical_sha256(
        b"abc", schema_version=SCHEMA_VERSION, digest_field=None
    ) == golden["structured_bytes_sha256"]


@pytest.mark.parametrize("payload", ["abc", 1, True, Path("abc")])
def test_raw_sha256_rejects_non_byte_payloads(payload: object) -> None:
    canonical = _canonical()

    with pytest.raises(canonical.InvalidBytePayloadError) as error:
        canonical.sha256_bytes(payload)

    assert error.value.code == "invalid_byte_payload"
    assert str(error.value) == "payload must be bytes, bytearray, or memoryview"


def test_canonical_identity_is_independent_of_python_hash_seed() -> None:
    golden = _golden()
    script = """
import json
from evonn_shared.canonical import canonical_sha256
from evonn_shared.rng import StreamName, derive_stream
value = {key: key for key in {"z", "a", "é"}}
print(json.dumps({
    "identity": canonical_sha256(value, schema_version="evonn.test/v1", digest_field=None),
    "streams": {name.value: derive_stream(42, name) for name in StreamName},
}, sort_keys=True))
"""
    outputs = []
    for hash_seed in ("1", "987654"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = hash_seed
        outputs.append(
            subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            ).stdout
        )

    assert outputs[0] == outputs[1]
    result = json.loads(outputs[0])
    assert result["streams"] == golden["rng"]["streams"]
    assert result["identity"] == "b9c0f85cc2c37ca0471e84554bf6c0e0035292e9761d14ab7233a257063983a3"
