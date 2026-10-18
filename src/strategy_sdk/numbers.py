"""Canonical finite decimal inputs and explicit quantity rounding."""

from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Context,
    Decimal,
    localcontext,
)

from .errors import DataError

DECIMAL_PRECISION = 34
ARITHMETIC_CONTEXT = Context(prec=DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)
ROUNDING = {"nearest": ROUND_HALF_UP, "up": ROUND_CEILING, "down": ROUND_FLOOR}


def decimal_value(value: object, name: str = "value") -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float, str)):
        raise DataError(f"{name} must be a finite decimal number")
    try:
        result = value if type(value) is Decimal else Decimal(str(value))
    except (ValueError, ArithmeticError):
        raise DataError(f"{name} must be a finite decimal number") from None
    if not result.is_finite():
        raise DataError(f"{name} must be finite")
    return result


def positive_decimal(value: object, name: str) -> Decimal:
    result = decimal_value(value, name)
    if result <= 0:
        raise DataError(f"{name} must be positive")
    return result


def positive_int(value: object, name: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise DataError(f"{name} must be an integer >= {minimum}")
    return value


def round_quantity(quantity: object, step: object = 1, *, rounding: str = "nearest") -> Decimal:
    quantity = decimal_value(quantity, "quantity")
    step = positive_decimal(step, "step")
    if quantity < 0 or rounding not in ROUNDING:
        raise DataError("Quantity must be nonnegative and rounding must be nearest, up, or down")
    with localcontext(ARITHMETIC_CONTEXT):
        return (quantity / step).to_integral_value(rounding=ROUNDING[rounding]) * step
