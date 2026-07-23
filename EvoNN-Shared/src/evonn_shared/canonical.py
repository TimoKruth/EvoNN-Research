"""Canonical typed identity encoding and SHA-256 helpers."""

from __future__ import annotations

import base64
from collections.abc import Mapping
import datetime as dt
import hashlib
import json
import math
import os
import re
import unicodedata

CANONICAL_ENCODING = "evonn-canonical-json-v1"
_SCHEMA_VERSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,127}$")
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")
_SIGNED_64_MIN = -(2**63)
_SIGNED_64_MAX = 2**63 - 1


type CanonicalScalar = None | bool | int | float | str | bytes
type CanonicalValue = (
    CanonicalScalar
    | list[CanonicalValue]
    | tuple[CanonicalValue, ...]
    | Mapping[str, CanonicalValue]
)
type _EncodedValue = list[object]


class CanonicalIdentityError(ValueError):
    """Base class for deterministic canonical identity contract errors."""

    code = "canonical_identity_error"


class InvalidSchemaVersionError(CanonicalIdentityError):
    code = "invalid_schema_version"


class UnsupportedCanonicalTypeError(CanonicalIdentityError):
    code = "unsupported_canonical_type"


class IntegerOutOfRangeError(CanonicalIdentityError):
    code = "integer_out_of_range"


class NonFiniteFloatError(CanonicalIdentityError):
    code = "nonfinite_float"


class InvalidMappingKeyError(CanonicalIdentityError):
    code = "invalid_mapping_key"


class NormalizedKeyCollisionError(CanonicalIdentityError):
    code = "normalized_key_collision"


class VolatileFieldError(CanonicalIdentityError):
    code = "volatile_field"


class AbsolutePathError(CanonicalIdentityError):
    code = "absolute_path"


class InvalidDigestFieldError(CanonicalIdentityError):
    code = "invalid_digest_field"


class InvalidBytePayloadError(CanonicalIdentityError):
    code = "invalid_byte_payload"


class InvalidUnicodeError(CanonicalIdentityError):
    code = "invalid_unicode"


def canonical_bytes(value: CanonicalValue, *, schema_version: str) -> bytes:
    """Encode a value as canonical typed JSON with its schema domain bound in."""

    return _canonical_bytes(value, schema_version=schema_version, omitted_top_level_key=None)


def canonical_sha256(
    value: CanonicalValue,
    *,
    schema_version: str,
    digest_field: str | None = "digest",
) -> str:
    """Hash canonical bytes, optionally omitting one normalized top-level map field."""

    normalized_digest_field = _normalize_digest_field(digest_field)
    payload = _canonical_bytes(
        value,
        schema_version=schema_version,
        omitted_top_level_key=normalized_digest_field,
    )
    return hashlib.sha256(payload).hexdigest()


def sha256_bytes(payload: bytes | bytearray | memoryview) -> str:
    """Hash an exact raw byte payload without applying the structured domain."""

    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise InvalidBytePayloadError("payload must be bytes, bytearray, or memoryview")
    return hashlib.sha256(bytes(payload)).hexdigest()


def _canonical_bytes(
    value: CanonicalValue,
    *,
    schema_version: str,
    omitted_top_level_key: str | None,
) -> bytes:
    _validate_schema_version(schema_version)
    encoded = [
        CANONICAL_ENCODING,
        schema_version,
        _encode(value, omitted_top_level_key=omitted_top_level_key, top_level=True),
    ]
    text = json.dumps(encoded, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise InvalidUnicodeError("canonical strings must contain valid Unicode scalar values") from error


def _validate_schema_version(schema_version: object) -> None:
    if not isinstance(schema_version, str) or _SCHEMA_VERSION_PATTERN.fullmatch(schema_version) is None:
        raise InvalidSchemaVersionError(
            "schema_version must match ^[a-z0-9][a-z0-9._/-]{0,127}$"
        )


def _normalize_digest_field(digest_field: object) -> str | None:
    if digest_field is None:
        return None
    if not isinstance(digest_field, str):
        raise InvalidDigestFieldError("digest_field must be a string or None")
    normalized = unicodedata.normalize("NFC", digest_field)
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError as error:
        raise InvalidUnicodeError("digest_field must contain valid Unicode scalar values") from error
    return normalized


def _encode(
    value: object,
    *,
    omitted_top_level_key: str | None = None,
    top_level: bool = False,
) -> _EncodedValue:
    if value is None:
        return ["n"]
    if isinstance(value, bool):
        return ["b", value]
    if isinstance(value, os.PathLike) or isinstance(value, (dt.date, dt.time, dt.timedelta, dt.tzinfo)):
        raise _unsupported_type(value)
    if type(value) is int:
        if not _SIGNED_64_MIN <= value <= _SIGNED_64_MAX:
            raise IntegerOutOfRangeError("canonical integers must be in the signed 64-bit range")
        return ["i", str(value)]
    if type(value) is float:
        if not math.isfinite(value):
            raise NonFiniteFloatError("canonical floats must be finite binary64 values")
        normalized = 0.0 if value == 0.0 else value
        return ["f", normalized.hex()]
    if isinstance(value, str):
        return ["s", unicodedata.normalize("NFC", value)]
    if isinstance(value, bytes):
        encoded = base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
        return ["y", encoded]
    if isinstance(value, (list, tuple)):
        return ["l", [_encode(item) for item in value]]
    if isinstance(value, Mapping):
        return _encode_mapping(
            value,
            omitted_top_level_key=omitted_top_level_key if top_level else None,
        )
    raise _unsupported_type(value)


def _encode_mapping(
    value: Mapping[object, object],
    *,
    omitted_top_level_key: str | None,
) -> _EncodedValue:
    normalized_items: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise InvalidMappingKeyError("canonical mapping keys must be strings")
        normalized_key = unicodedata.normalize("NFC", key)
        if normalized_key in normalized_items:
            raise NormalizedKeyCollisionError(
                f"mapping keys collide after NFC normalization: {normalized_key!r}"
            )
        normalized_items[normalized_key] = item

    try:
        ordered_keys = sorted(normalized_items, key=lambda key: key.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise InvalidUnicodeError("canonical mapping keys must contain valid Unicode scalar values") from error

    encoded_items: list[list[object]] = []
    for key in ordered_keys:
        item = normalized_items[key]
        _validate_field(key, item)
        encoded_item = _encode(item)
        if key != omitted_top_level_key:
            encoded_items.append([key, encoded_item])
    return ["m", encoded_items]


def _validate_field(key: str, value: object) -> None:
    if key == "timestamp" or key.endswith("_timestamp") or key.endswith("_at"):
        raise VolatileFieldError(f"volatile field is forbidden in canonical identity: {key!r}")
    if (key == "path" or key.endswith("_path")) and isinstance(value, str):
        if _is_absolute_or_drive_qualified_path(value):
            raise AbsolutePathError(
                f"absolute or drive-qualified path is forbidden for field: {key!r}"
            )


def _is_absolute_or_drive_qualified_path(value: str) -> bool:
    return str.startswith(value, ("/", "\\")) or _WINDOWS_DRIVE_PATTERN.match(value) is not None


def _unsupported_type(value: object) -> UnsupportedCanonicalTypeError:
    value_type = type(value)
    return UnsupportedCanonicalTypeError(
        f"unsupported canonical value type: {value_type.__module__}.{value_type.__qualname__}"
    )


__all__ = [
    "AbsolutePathError",
    "CANONICAL_ENCODING",
    "CanonicalIdentityError",
    "CanonicalScalar",
    "CanonicalValue",
    "IntegerOutOfRangeError",
    "InvalidBytePayloadError",
    "InvalidDigestFieldError",
    "InvalidMappingKeyError",
    "InvalidSchemaVersionError",
    "InvalidUnicodeError",
    "NonFiniteFloatError",
    "NormalizedKeyCollisionError",
    "UnsupportedCanonicalTypeError",
    "VolatileFieldError",
    "canonical_bytes",
    "canonical_sha256",
    "sha256_bytes",
]
