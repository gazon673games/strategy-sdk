"""Comparable cost estimates supplied to strategy funding decisions."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from .errors import DataError
from .models import Instrument
from .numbers import ARITHMETIC_CONTEXT, decimal_value


@dataclass(frozen=True, slots=True)
class CostPolicy:
    commission_bps: Decimal = Decimal(0)
    commission_per_unit: Decimal = Decimal(0)
    slippage_ticks: Decimal = Decimal(0)
    spread_ticks: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        for name in ("commission_bps", "commission_per_unit", "slippage_ticks", "spread_ticks"):
            value = decimal_value(getattr(self, name), name)
            if value < 0:
                raise DataError("Execution cost inputs must be nonnegative")
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class ExecutionCosts:
    commission: Decimal
    market: Decimal

    def __post_init__(self) -> None:
        for name in ("commission", "market"):
            value = decimal_value(getattr(self, name), name)
            if value < 0:
                raise DataError("Estimated costs must be nonnegative")
            object.__setattr__(self, name, value)

    @property
    def total(self) -> Decimal:
        with localcontext(ARITHMETIC_CONTEXT):
            return self.commission + self.market


def estimate_costs(quantity, price, instrument: Instrument, policy: CostPolicy) -> ExecutionCosts:
    quantity = decimal_value(quantity, "cost quantity")
    price = decimal_value(price, "cost price")
    if quantity < 0:
        raise DataError("Cost quantity must be nonnegative")
    with localcontext(ARITHMETIC_CONTEXT):
        ticks = policy.slippage_ticks + policy.spread_ticks
        if quantity and ticks and instrument.price_tick is None:
            raise DataError("Price tick is required to estimate market costs")
        commission = quantity * (
            abs(price) * instrument.multiplier * policy.commission_bps / 10000
            + policy.commission_per_unit
        )
        market = quantity * ticks * (instrument.price_tick or Decimal(0)) * instrument.multiplier
        return ExecutionCosts(commission, market)


def required_funds(
    quantity, initial_margin_per_unit, costs: ExecutionCosts, *, reserve=0
) -> Decimal:
    quantity = decimal_value(quantity, "funding quantity")
    margin = decimal_value(initial_margin_per_unit, "initial margin")
    reserve = decimal_value(reserve, "reserve")
    if min(quantity, margin, reserve) < 0:
        raise DataError("Funding inputs must be nonnegative")
    with localcontext(ARITHMETIC_CONTEXT):
        return quantity * margin + costs.total + reserve
