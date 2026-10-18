"""Explicit JSON state and feature values. No arbitrary object serialization."""

import math
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from .errors import DataError
from .time import aware_datetime


def json_copy(value: object, *, depth: int = 0):
    if depth > 32:
        raise DataError("JSON data exceeds the nesting limit")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, list):
        return [json_copy(item, depth=depth + 1) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: json_copy(item, depth=depth + 1) for key, item in value.items()}
    raise DataError("State and features must contain finite JSON values with string keys")


def _feature_value(value, depth=0):
    if depth > 32:
        raise DataError("Features exceed the nesting limit")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise DataError("Feature numbers must be finite")
        return str(value)
    if isinstance(value, datetime):
        return aware_datetime(value, "feature timestamp").isoformat()
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise DataError("Feature keys must be strings")
        return {key: _feature_value(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_feature_value(item, depth + 1) for item in value]
    return json_copy(value, depth=depth)


def feature_snapshot(**values) -> dict:
    return _feature_value(values)
