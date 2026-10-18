"""Declared primitive parameters, with no environment or file reads."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from .errors import DataError, ParameterError
from .numbers import decimal_value

PARAM_TYPES = {"int", "float", "decimal", "str", "bool"}
BOOLEAN_VALUES = {
    "true": True,
    "1": True,
    "yes": True,
    "on": True,
    "false": False,
    "0": False,
    "no": False,
    "off": False,
}


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    name: str
    param_type: str
    default: object = None
    required: bool = False
    min_value: object = None
    max_value: object = None
    choices: tuple = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name.strip()
            or not isinstance(self.param_type, str)
            or self.param_type not in PARAM_TYPES
        ):
            raise ParameterError("Invalid parameter name or type")
        if not isinstance(self.required, bool):
            raise ParameterError("Parameter required must be boolean")
        object.__setattr__(self, "choices", tuple(self.choices))
        if self.param_type not in {"int", "float", "decimal"} and (
            self.min_value is not None or self.max_value is not None
        ):
            raise ParameterError("Only numeric parameters can declare bounds")
        try:
            for name in ("min_value", "max_value"):
                if getattr(self, name) is not None:
                    object.__setattr__(self, name, decimal_value(getattr(self, name), name))
        except DataError as error:
            raise ParameterError(str(error)) from error
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ParameterError("Parameter minimum exceeds maximum")


def _cast(value: object, spec: ParameterSpec) -> object:
    if spec.param_type == "str":
        if not isinstance(value, str):
            raise ParameterError(f"{spec.name} must be a string")
        return value
    if spec.param_type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (str, int)):
            normalized = str(value).lower()
            if normalized in BOOLEAN_VALUES:
                return BOOLEAN_VALUES[normalized]
        raise ParameterError(f"{spec.name} must be boolean")
    try:
        number = decimal_value(value, spec.name)
    except DataError as error:
        raise ParameterError(str(error)) from error
    if spec.param_type == "int":
        if number != number.to_integral_value():
            raise ParameterError(f"{spec.name} must be an integer without a fractional part")
        return int(number)
    if spec.param_type == "float":
        result = float(number)
        if not isfinite(result):
            raise ParameterError(f"{spec.name} must fit a finite float")
        return result
    return number


def validate_strategy_params(raw: Mapping | None, specs: tuple[ParameterSpec, ...]) -> dict:
    if raw is not None and not isinstance(raw, Mapping):
        raise ParameterError("Strategy parameters must be a mapping")
    raw = dict(raw or {})
    names = [spec.name for spec in specs]
    if len(set(names)) != len(names):
        raise ParameterError("Parameter names must be unique")
    if any(not isinstance(name, str) for name in raw):
        raise ParameterError("Parameter keys must be strings")
    unknown = sorted(set(raw) - set(names))
    if unknown:
        raise ParameterError(f"Unknown parameters: {', '.join(unknown)}")
    result = {}
    for spec in specs:
        value = raw.get(spec.name, spec.default)
        if value is None:
            if spec.required:
                raise ParameterError(f"Missing required parameter: {spec.name}")
            result[spec.name] = None
            continue
        value = _cast(value, spec)
        if spec.min_value is not None or spec.max_value is not None:
            number = decimal_value(value)
            if spec.min_value is not None and number < spec.min_value:
                raise ParameterError(f"{spec.name} is below its minimum")
            if spec.max_value is not None and number > spec.max_value:
                raise ParameterError(f"{spec.name} exceeds its maximum")
        if spec.choices and value not in spec.choices:
            raise ParameterError(f"{spec.name} is not an allowed choice")
        result[spec.name] = value
    return result
