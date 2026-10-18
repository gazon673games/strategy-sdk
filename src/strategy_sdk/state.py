"""Versioned JSON state. The host owns persistence and commit timing."""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ._version import SDK_API_VERSION
from .errors import DataError, StateError
from .json_data import json_copy
from .time import aware_datetime


def _unique_keys(pairs) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise StateError("State JSON contains duplicate keys")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class StateEnvelope:
    instance_id: str
    revision: str
    updated_at: datetime
    data: dict
    sdk_api_version: int = SDK_API_VERSION

    def __post_init__(self) -> None:
        try:
            identity = UUID(self.instance_id)
            if identity.int == 0:
                raise ValueError
            object.__setattr__(self, "instance_id", str(identity))
            object.__setattr__(
                self, "updated_at", aware_datetime(self.updated_at, "state updated_at")
            )
            if not isinstance(self.data, dict):
                raise DataError("State data must be a dictionary")
            object.__setattr__(self, "data", json_copy(self.data))
        except (ValueError, TypeError, AttributeError, DataError) as error:
            raise StateError("Invalid state identity, timestamp, or data") from error
        if not isinstance(self.revision, str) or not re.fullmatch(r"[0-9a-f]{64}", self.revision):
            raise StateError("State revision must be a SHA256 fingerprint")
        if type(self.sdk_api_version) is not int or self.sdk_api_version != SDK_API_VERSION:
            raise StateError("Unsupported state SDK API version")

    def to_json(self) -> str:
        return json.dumps(
            {
                "sdk_api_version": self.sdk_api_version,
                "instance_id": self.instance_id,
                "revision": self.revision,
                "updated_at": self.updated_at.isoformat(),
                "data": json_copy(self.data),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, text: str, *, max_bytes: int = 1048576) -> "StateEnvelope":
        try:
            if type(max_bytes) is not int or max_bytes < 1:
                raise StateError("State size limit must be a positive integer")
            if not isinstance(text, str) or len(text.encode("utf-8")) > max_bytes:
                raise StateError("State JSON exceeds its size limit")
            raw = json.loads(text, object_pairs_hook=_unique_keys)
            required = {"sdk_api_version", "instance_id", "revision", "updated_at", "data"}
            if not isinstance(raw, dict) or set(raw) != required:
                raise StateError("State envelope has missing or unknown fields")
            raw["updated_at"] = datetime.fromisoformat(raw["updated_at"])
            return cls(**raw)
        except (ValueError, TypeError, RecursionError, DataError) as error:
            raise StateError("State JSON is invalid") from error

    def restore(self, instance_id: str, revision: str) -> dict:
        try:
            identity = str(UUID(instance_id))
        except (ValueError, TypeError, AttributeError) as error:
            raise StateError("Invalid expected instance UUID") from error
        if identity != self.instance_id or revision != self.revision:
            raise StateError("State belongs to another instance or strategy revision")
        return json_copy(self.data)
