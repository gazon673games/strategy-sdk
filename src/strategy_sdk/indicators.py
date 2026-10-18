"""Decimal indicators over visible sequences, independent of storage engines.

EMA seeds with the first complete SMA. ATR is the simple mean of true ranges.
RSI uses simple window averages. Nulls are rejected rather than interpolated.
"""

from collections.abc import Sequence
from decimal import Decimal, localcontext

from .bars import Bar
from .numbers import ARITHMETIC_CONTEXT, decimal_value, positive_int


def _tail(values: Sequence, window: int) -> tuple[Decimal, ...] | None:
    positive_int(window, "window")
    if len(values) < window:
        return None
    return tuple(decimal_value(value, "indicator value") for value in values[-window:])


def sma(values: Sequence, window: int) -> Decimal | None:
    values = _tail(values, window)
    if values is None:
        return None
    with localcontext(ARITHMETIC_CONTEXT):
        return sum(values, Decimal(0)) / window


def rolling_sma(values: Sequence, window: int) -> tuple[Decimal | None, ...]:
    positive_int(window, "window")
    numbers = [decimal_value(value, "indicator value") for value in values]
    result: list[Decimal | None] = []
    with localcontext(ARITHMETIC_CONTEXT):
        total = Decimal(0)
        for index, value in enumerate(numbers):
            total += value
            if index >= window:
                total -= numbers[index - window]
            result.append(total / window if index + 1 >= window else None)
    return tuple(result)


def ema(values: Sequence, window: int) -> Decimal | None:
    positive_int(window, "window")
    if len(values) < window:
        return None
    with localcontext(ARITHMETIC_CONTEXT):
        result = sma(values[:window], window)
        alpha = Decimal(2) / (window + 1)
        for value in values[window:]:
            result += alpha * (decimal_value(value, "indicator value") - result)
        return result


def rolling_high(values: Sequence, window: int) -> Decimal | None:
    tail = _tail(values, window)
    return max(tail) if tail is not None else None


def rolling_low(values: Sequence, window: int) -> Decimal | None:
    tail = _tail(values, window)
    return min(tail) if tail is not None else None


def rolling_std(values: Sequence, window: int) -> Decimal | None:
    tail = _tail(values, window)
    if tail is None:
        return None
    with localcontext(ARITHMETIC_CONTEXT):
        mean = sum(tail, Decimal(0)) / window
        return (sum((value - mean) ** 2 for value in tail) / window).sqrt()


def rsi(values: Sequence, window: int = 14) -> Decimal | None:
    positive_int(window, "window")
    tail = _tail(values, window + 1)
    if tail is None:
        return None
    with localcontext(ARITHMETIC_CONTEXT):
        changes = [
            current - previous for previous, current in zip(tail[:-1], tail[1:], strict=True)
        ]
        gains = sum((max(change, Decimal(0)) for change in changes), Decimal(0))
        losses = sum((max(-change, Decimal(0)) for change in changes), Decimal(0))
        if not gains and not losses:
            return Decimal(50)
        if not losses:
            return Decimal(100)
        return Decimal(100) - Decimal(100) / (1 + gains / losses)


def atr(bars: Sequence[Bar], window: int = 14) -> Decimal | None:
    positive_int(window, "window")
    if len(bars) < window + 1:
        return None
    tail = bars[-window - 1 :]
    with localcontext(ARITHMETIC_CONTEXT):
        ranges = [
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
            for previous, current in zip(tail[:-1], tail[1:], strict=True)
        ]
        return sum(ranges, Decimal(0)) / window
