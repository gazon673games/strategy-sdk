"""Algorithm identity and finite data requirements known before evaluation."""

from dataclasses import dataclass
from datetime import time

from ._version import SDK_API_VERSION
from .errors import DataError, ParameterError
from .models import identifier
from .numbers import positive_int
from .parameters import ParameterSpec
from .time import normalize_timeframe, resolve_timezone


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    name: str
    version: str = "1"
    params: tuple[ParameterSpec, ...] = ()
    sdk_api_version: int = SDK_API_VERSION

    def __post_init__(self) -> None:
        identifier(self.name, "strategy name")
        identifier(self.version, "strategy version")
        if type(self.sdk_api_version) is not int or self.sdk_api_version != SDK_API_VERSION:
            raise ParameterError("Unsupported strategy SDK API version")
        object.__setattr__(self, "params", tuple(self.params))
        if any(not isinstance(spec, ParameterSpec) for spec in self.params):
            raise ParameterError("Strategy params must contain ParameterSpec values")
        names = [spec.name for spec in self.params]
        if len(names) != len(set(names)):
            raise ParameterError("Parameter names must be unique")


@dataclass(frozen=True, slots=True)
class DataRequirements:
    timeframe: str
    history_bars: int
    warmup_bars: int = 0
    timezone: str = "UTC"
    session_start: time | None = None
    minimum_session_bars: int = 0
    decision_times: tuple[time, ...] = ()
    insufficient_history: str = "error"
    missing_decision_policy: str = "skip"

    def __post_init__(self) -> None:
        object.__setattr__(self, "timeframe", normalize_timeframe(self.timeframe))
        positive_int(self.history_bars, "history_bars")
        positive_int(self.warmup_bars, "warmup_bars", allow_zero=True)
        positive_int(self.minimum_session_bars, "minimum_session_bars", allow_zero=True)
        if max(self.warmup_bars, self.minimum_session_bars) > self.history_bars:
            raise DataError("History window cannot be smaller than the required warmup")
        resolve_timezone(self.timezone)
        object.__setattr__(self, "decision_times", tuple(self.decision_times))
        clocks = self.decision_times + (
            (self.session_start,) if self.session_start is not None else ()
        )
        if any(not isinstance(clock, time) or clock.tzinfo is not None for clock in clocks):
            raise DataError(
                "Session and decision times must be naive wall-clock times in the declared zone"
            )
        if len(set(self.decision_times)) != len(self.decision_times):
            raise DataError("Decision times must be unique")
        if self.minimum_session_bars and self.session_start is None:
            raise DataError("Minimum session bars requires an explicit session start")
        if self.insufficient_history not in {"error", "flat", "skip"}:
            raise DataError("Insufficient history policy must be error, flat, or skip")
        if self.missing_decision_policy not in {"close", "carry", "skip"}:
            raise DataError("Missing decision policy must be close, carry, or skip")

    def as_dict(self) -> dict:
        return {
            "timeframe": self.timeframe,
            "history_bars": self.history_bars,
            "warmup_bars": self.warmup_bars,
            "timezone": self.timezone,
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "minimum_session_bars": self.minimum_session_bars,
            "decision_times": [clock.isoformat() for clock in self.decision_times],
            "insufficient_history": self.insufficient_history,
            "missing_decision_policy": self.missing_decision_policy,
        }
