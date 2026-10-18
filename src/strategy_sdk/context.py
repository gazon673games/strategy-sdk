"""Bounded snapshot consumed by one decision, with no future-data access."""

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal

from .bars import Bar
from .errors import DataError, InsufficientHistory
from .indicators import ema, sma
from .models import AccountSnapshot, Instrument, Position
from .numbers import positive_int
from .time import aware_datetime, normalize_timeframe, resolve_timezone

PRICE_COLUMNS = {"open", "high", "low", "close", "volume"}
TIME_COLUMNS = {"ts": "opened_at", "opened_at": "opened_at", "closed_at": "closed_at"}


def _column_name(column: str) -> str:
    if column not in PRICE_COLUMNS and column not in TIME_COLUMNS:
        raise DataError("Unknown history column")
    return TIME_COLUMNS.get(column, column)


@dataclass(frozen=True, slots=True)
class StrategyContext:
    as_of: datetime
    instrument: Instrument
    timeframe: str
    bars: tuple[Bar, ...]
    timezone: str = "UTC"
    position: Position | None = None
    account: AccountSnapshot | None = None
    state: dict | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", aware_datetime(self.as_of, "as_of"))
        if not isinstance(self.instrument, Instrument):
            raise DataError("Context requires an Instrument")
        object.__setattr__(self, "timeframe", normalize_timeframe(self.timeframe))
        resolve_timezone(self.timezone)
        object.__setattr__(self, "bars", tuple(self.bars))
        previous = None
        for bar in self.bars:
            if not isinstance(bar, Bar):
                raise DataError("Context history must contain Bar values")
            if bar.closed_at > self.as_of:
                raise DataError("History contains an unfinished or future bar")
            if previous is not None and bar.opened_at < previous.closed_at:
                raise DataError("History contains unsorted, overlapping, or duplicate bars")
            previous = bar
        if self.position is not None:
            if (
                not isinstance(self.position, Position)
                or self.position.symbol != self.instrument.symbol
            ):
                raise DataError("Position must refer to the context instrument")
        if self.account is not None and not isinstance(self.account, AccountSnapshot):
            raise DataError("Context account must be an AccountSnapshot")

    @property
    def current_ts(self) -> datetime:
        return self.as_of.astimezone(resolve_timezone(self.timezone))

    @property
    def current_time(self) -> time:
        return self.current_ts.time()

    @property
    def current_date(self):
        return self.current_ts.date()

    @property
    def weekday(self) -> int:
        return self.current_ts.weekday()

    @property
    def active_contract(self) -> str:
        return self.instrument.symbol

    @property
    def previous_position(self) -> int:
        """Normalized direction, never the number of contracts."""
        return self.position.direction if self.position else 0

    @property
    def position_quantity(self) -> Decimal:
        return self.position.quantity if self.position else Decimal(0)

    def history(self) -> tuple[Bar, ...]:
        return self.bars

    def history_tail(self, limit: int) -> tuple[Bar, ...]:
        positive_int(limit, "history limit")
        return self.bars[-limit:]

    def current_bar(self) -> Bar:
        if not self.bars:
            raise InsufficientHistory("No completed bars are available")
        return self.bars[-1]

    def series(self, column: str) -> tuple:
        name = _column_name(column)
        return tuple(getattr(bar, name) for bar in self.bars)

    def _bar_index(self, offset: int) -> int:
        if isinstance(offset, bool) or not isinstance(offset, int) or offset > 0:
            raise DataError("History offset must be a nonpositive integer")
        index = len(self.bars) - 1 + offset
        if index < 0:
            raise InsufficientHistory("History offset precedes the supplied window")
        return index

    def value(self, column: str, *, offset: int = 0):
        index = self._bar_index(offset)
        return getattr(self.bars[index], _column_name(column))

    def session_history(self, start: time = time(0)) -> tuple[Bar, ...]:
        if not isinstance(start, time) or start.tzinfo is not None:
            raise DataError("Session start must be a naive wall-clock time")
        zone = resolve_timezone(self.timezone)
        session_date = self.as_of.astimezone(zone).date()
        result = []
        for bar in self.bars:
            opened_at = bar.opened_at.astimezone(zone)
            if opened_at.date() == session_date and opened_at.time() >= start:
                result.append(bar)
        return tuple(result)

    def sma(self, column: str, window: int, *, offset: int = 0) -> Decimal | None:
        values = self.series(column)
        if not self.bars and type(offset) is int and offset == 0:
            return sma(values, window)
        end = self._bar_index(offset) + 1
        return sma(values[:end], window)

    def ema(self, column: str, window: int) -> Decimal | None:
        return ema(self.series(column), window)

    def contiguous(self, count: int) -> bool:
        positive_int(count, "confirmation count")
        tail = self.history_tail(count)
        return len(tail) == count and all(
            previous.closed_at == current.opened_at
            for previous, current in zip(tail[:-1], tail[1:], strict=True)
        )
