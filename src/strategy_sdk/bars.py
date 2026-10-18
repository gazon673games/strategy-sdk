"""One-instrument bars. Closing times determine data availability."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .errors import DataError
from .numbers import decimal_value
from .time import aware_datetime


@dataclass(frozen=True, slots=True)
class Bar:
    opened_at: datetime
    closed_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "opened_at", aware_datetime(self.opened_at, "opened_at"))
        object.__setattr__(self, "closed_at", aware_datetime(self.closed_at, "closed_at"))
        if self.closed_at <= self.opened_at:
            raise DataError("Bar must close after its opening time")
        for name in ("open", "high", "low", "close", "volume"):
            object.__setattr__(self, name, decimal_value(getattr(self, name), name))
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise DataError("OHLC values are inconsistent")
        if self.volume < 0:
            raise DataError("Volume must be nonnegative")
