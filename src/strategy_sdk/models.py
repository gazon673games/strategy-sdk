"""Small broker-neutral snapshots supplied by the host."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .errors import DataError
from .numbers import decimal_value, positive_decimal
from .time import aware_datetime


def identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"{name} must be a nonempty string")
    return value


@dataclass(frozen=True, slots=True)
class Instrument:
    symbol: str
    currency: str
    multiplier: Decimal = Decimal(1)
    quantity_step: Decimal = Decimal(1)
    price_tick: Decimal | None = None

    def __post_init__(self) -> None:
        identifier(self.symbol, "symbol")
        identifier(self.currency, "currency")
        for name in ("multiplier", "quantity_step"):
            object.__setattr__(self, name, positive_decimal(getattr(self, name), name))
        if self.price_tick is not None:
            object.__setattr__(self, "price_tick", positive_decimal(self.price_tick, "price_tick"))


@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    quantity: Decimal

    def __post_init__(self) -> None:
        identifier(self.symbol, "symbol")
        object.__setattr__(self, "quantity", decimal_value(self.quantity, "quantity"))

    @property
    def direction(self) -> int:
        return (self.quantity > 0) - (self.quantity < 0)


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    currency: str
    equity: Decimal
    available_funds: Decimal | None = None

    def __post_init__(self) -> None:
        identifier(self.currency, "currency")
        object.__setattr__(self, "equity", decimal_value(self.equity, "equity"))
        if self.available_funds is not None:
            object.__setattr__(
                self, "available_funds", decimal_value(self.available_funds, "available_funds")
            )


@dataclass(frozen=True, slots=True)
class Fill:
    id: str
    timestamp: datetime
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    position_after: Decimal | None = None
    liquidated: bool = False

    def __post_init__(self) -> None:
        identifier(self.id, "fill id")
        identifier(self.symbol, "symbol")
        object.__setattr__(self, "timestamp", aware_datetime(self.timestamp, "fill timestamp"))
        if self.side not in {"BUY", "SELL"}:
            raise DataError("Fill side must be BUY or SELL")
        object.__setattr__(self, "quantity", positive_decimal(self.quantity, "fill quantity"))
        object.__setattr__(self, "price", decimal_value(self.price, "fill price"))
        if type(self.liquidated) is not bool:
            raise DataError("Fill liquidated must be boolean")
        if self.position_after is not None:
            quantity = decimal_value(self.position_after, "position_after")
            if self.liquidated and quantity != 0:
                raise DataError("A liquidated fill must leave a zero position")
            object.__setattr__(self, "position_after", quantity)
