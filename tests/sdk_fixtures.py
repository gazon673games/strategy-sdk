from datetime import datetime, timedelta, timezone
from pathlib import Path

from strategy_sdk import (
    Bar,
    Instrument,
    StrategyContext,
)

CUTOFF = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


def bars(values=(10, 11, 12, 13), *, cutoff=CUTOFF):
    return tuple(
        Bar(
            cutoff - timedelta(minutes=5 * (len(values) - index)),
            cutoff - timedelta(minutes=5 * (len(values) - index - 1)),
            value,
            value,
            value,
            value,
        )
        for index, value in enumerate(values)
    )


def context(values=(10, 11, 12, 13), **kwargs):
    return StrategyContext(CUTOFF, Instrument("TEST", "USD"), "M5", bars(values), **kwargs)


HEADER = """from strategy_sdk import (
    DataRequirements, ParameterSpec, StrategyMetadata, long_decision, short_decision
)
STRATEGY_METADATA = StrategyMetadata("fixture", params=(
    ParameterSpec("period", "int", default=4, min_value=1, max_value=100),
))
def data_requirements(params):
    return DataRequirements("M5", params["period"], warmup_bars=params["period"])
"""


def write_strategy(
    root, body="def generate_signal(ctx, params):\n    return long_decision(reason='test')\n"
):
    path = Path(root) / "strategy.py"
    path.write_text(HEADER + body, encoding="utf-8")
    return path
