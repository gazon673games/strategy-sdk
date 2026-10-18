import unittest
from decimal import ROUND_DOWN, Decimal, localcontext

from sdk_fixtures import bars, context

from strategy_sdk import (
    CostPolicy,
    DataError,
    Instrument,
    ParameterError,
    ParameterSpec,
    addition_quantity,
    atr,
    ema,
    entry_quantity,
    estimate_costs,
    required_funds,
    rolling_sma,
    round_quantity,
    rsi,
    sma,
    validate_strategy_params,
)


class ParameterTests(unittest.TestCase):
    def test_declared_types_defaults_and_unknown_keys(self):
        specs = (
            ParameterSpec("period", "int", default=50, min_value=1),
            ParameterSpec("percent", "decimal", default="250"),
            ParameterSpec("enabled", "bool", default=False),
        )
        result = validate_strategy_params({"period": "9", "enabled": "true"}, specs)
        self.assertEqual(result, {"period": 9, "percent": Decimal(250), "enabled": True})
        for raw in (
            {"period": "3.5"},
            {"period": True},
            {"period": 0},
            {"percent": "NaN"},
            {"enabled": "maybe"},
            {"typo": 1},
        ):
            with self.subTest(raw=raw), self.assertRaises(ParameterError):
                validate_strategy_params(raw, specs)
        with self.assertRaises(ParameterError):
            validate_strategy_params({}, (ParameterSpec("required", "str", required=True),))


class MathTests(unittest.TestCase):
    def test_nine_bars_have_their_own_sma50(self):
        snapshot = context(tuple(range(1, 59)))
        actual = [snapshot.sma("close", 50, offset=offset) for offset in range(-8, 1)]
        self.assertEqual(actual, [Decimal("25.5") + index for index in range(9)])
        self.assertEqual(rolling_sma(snapshot.series("close"), 50)[-9:], tuple(actual))
        self.assertIsNone(sma([1, 2], 3))
        self.assertIsNone(context(()).sma("close", 50))

    def test_decimal_rounding_is_independent_of_host_context(self):
        expected = sma([1, 0, 0], 3)
        with localcontext() as host:
            host.prec, host.rounding = 2, ROUND_DOWN
            self.assertEqual(sma([1, 0, 0], 3), expected)
            self.assertEqual(round_quantity("7.5", 5), Decimal(10))
        self.assertEqual(str(expected), "0.3333333333333333333333333333333333")

    def test_quantity_rounding_supports_fractional_steps_and_zero_entry(self):
        instrument = Instrument("TEST", "USD", quantity_step="0.1")
        self.assertEqual(entry_quantity(100, 3, instrument), Decimal("33.3"))
        self.assertEqual(entry_quantity(0, 3, instrument), Decimal(0))
        self.assertEqual(round_quantity("0.5"), Decimal(1))
        self.assertEqual(addition_quantity(-3, 25), Decimal(1))
        self.assertEqual(addition_quantity(40, 25), Decimal(10))
        with self.assertRaises(DataError):
            entry_quantity(100, 0, instrument)

    def test_costs_include_margin_commission_spread_slippage_and_reserve(self):
        instrument = Instrument("TEST", "EUR", multiplier=1000, price_tick="0.001")
        costs = estimate_costs(10, 12, instrument, CostPolicy("0.5", 1, 1, 1))
        self.assertEqual((costs.commission, costs.market), (Decimal(16), Decimal(20)))
        self.assertEqual(required_funds(10, 1500, costs, reserve=100), Decimal(15136))
        with self.assertRaises(DataError):
            estimate_costs(1, 12, Instrument("TEST", "EUR"), CostPolicy(slippage_ticks=1))

    def test_indicator_seed_and_gap_semantics(self):
        self.assertEqual(ema([1, 2, 3, 4], 3), Decimal(3))
        self.assertEqual(rsi([1, 2, 3], 2), Decimal(100))
        self.assertEqual(rsi([3, 2, 1], 2), Decimal(0))
        self.assertEqual(rsi([1, 1, 1], 2), Decimal(50))
        self.assertEqual(atr(bars((10, 15)), 1), Decimal(5))
