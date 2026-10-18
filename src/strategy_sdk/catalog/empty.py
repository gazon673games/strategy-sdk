"""Blank callback for contract checks; it never submits a trading signal."""

from strategy_sdk import DataRequirements, ParameterSpec, StrategyMetadata, hold_decision

STRATEGY_METADATA = StrategyMetadata(
    "empty",
    params=(
        ParameterSpec("timeframe", "str", default="M5"),
        ParameterSpec("timezone", "str", default="UTC"),
    ),
)


def data_requirements(params):
    return DataRequirements(params["timeframe"], 1, timezone=params["timezone"])


def generate_signal(ctx, params):
    return hold_decision(reason="no_signal")
