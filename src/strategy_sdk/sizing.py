"""Pure sizing rules. Currency conversion and account allocation belong to hosts."""

from decimal import Decimal, localcontext

from .errors import DataError
from .models import Instrument
from .numbers import ARITHMETIC_CONTEXT, decimal_value, positive_decimal, round_quantity


def entry_quantity(
    equity, price, instrument: Instrument, percent=100, *, rounding: str = "nearest"
) -> Decimal:
    equity = decimal_value(equity, "equity")
    price = positive_decimal(price, "price")
    percent = decimal_value(percent, "entry percent")
    if percent < 0:
        raise DataError("Entry percent must be nonnegative")
    with localcontext(ARITHMETIC_CONTEXT):
        requested = max(equity, Decimal(0)) * percent / 100 / (price * instrument.multiplier)
        return round_quantity(requested, instrument.quantity_step, rounding=rounding)


def addition_quantity(current_quantity, percent, step=1, *, rounding: str = "up") -> Decimal:
    current_quantity = decimal_value(current_quantity, "current quantity")
    percent = decimal_value(percent, "addition percent")
    if percent < 0:
        raise DataError("Addition percent must be nonnegative")
    with localcontext(ARITHMETIC_CONTEXT):
        return round_quantity(abs(current_quantity) * percent / 100, step, rounding=rounding)
