import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from sdk_fixtures import CUTOFF, HEADER, context, write_strategy

from strategy_sdk import (
    DataError,
    DecisionError,
    Fill,
    InsufficientHistory,
    StrategyError,
    StrategyLoadError,
    load_strategy,
)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_same_inputs_match_across_locations_and_source_replacement_is_pinned(self):
        path = write_strategy(self.root)
        first = load_strategy(path)
        other = self.root / "other.py"
        other.write_bytes(path.read_bytes())
        second = load_strategy(other)
        self.assertEqual(first.revision, second.revision)
        self.assertEqual(first.evaluate(context()), second.evaluate(context()))
        path.write_text(
            HEADER
            + "def generate_signal(ctx, params):\n    return short_decision(reason='changed')\n",
            encoding="utf-8",
        )
        changed = load_strategy(path)
        self.assertEqual(first.evaluate(context()).decision.target, 1)
        self.assertEqual(changed.evaluate(context()).decision.target, -1)
        self.assertNotEqual(first.revision, changed.revision)
        self.assertNotEqual(first.revision, load_strategy(other, {"period": 3}).revision)
        self.assertFalse(any(name.startswith("_strategy_sdk_") for name in sys.modules))

    def test_state_is_explicit_and_initialize_is_not_repeated_after_restore(self):
        path = write_strategy(
            self.root,
            """def initialize(params):
    return {"initializations": 1, "calls": 0}
def generate_signal(ctx, params):
    ctx.state["calls"] += 1
    return long_decision(reason="test")
""",
        )
        strategy = load_strategy(path)
        initial = strategy.evaluate(context())
        next_run = strategy.evaluate(replace(context(), state=initial.state))
        self.assertEqual(initial.state, {"initializations": 1, "calls": 1})
        self.assertEqual(next_run.state, {"initializations": 1, "calls": 2})
        self.assertEqual(strategy.evaluate(context()).state, initial.state)

    def test_failure_does_not_mutate_the_original_state(self):
        path = write_strategy(
            self.root,
            """def generate_signal(ctx, params):
    ctx.state["nested"]["value"] = 99
    raise ValueError("Synthetic strategy failure")
""",
        )
        snapshot = context(state={"nested": {"value": 1}})
        with self.assertRaises(StrategyError):
            load_strategy(path).evaluate(snapshot)
        self.assertEqual(snapshot.state, {"nested": {"value": 1}})

    def test_insufficient_history_is_explicit_and_does_not_call_strategy(self):
        for policy, kind in (("error", None), ("flat", "TARGET"), ("skip", "SKIP")):
            source = HEADER.replace(
                'warmup_bars=params["period"]',
                f'warmup_bars=params["period"], insufficient_history="{policy}"',
            )
            path = self.root / "strategy.py"
            path.write_text(
                source
                + "def generate_signal(ctx, params):\n    raise AssertionError('Must not run')\n",
                encoding="utf-8",
            )
            strategy = load_strategy(path)
            with self.subTest(policy=policy):
                if kind is None:
                    with self.assertRaises(InsufficientHistory):
                        strategy.evaluate(context((10, 11)))
                else:
                    result = strategy.evaluate(context((10, 11)))
                    self.assertEqual(result.decision.kind, kind)
                    self.assertEqual(result.decision.reason, "insufficient_history")
                    if policy == "flat":
                        self.assertEqual(result.decision.target, 0)

    def test_session_requirement_cannot_use_bars_before_session_start(self):
        source = HEADER.replace(
            'warmup_bars=params["period"]',
            'warmup_bars=4, session_start=__import__("datetime").time(11, 50), '
            "minimum_session_bars=4",
        )
        path = self.root / "strategy.py"
        path.write_text(
            source + "def generate_signal(ctx, params):\n    return long_decision(reason='test')\n",
            encoding="utf-8",
        )
        with self.assertRaises(InsufficientHistory):
            load_strategy(path).evaluate(context())

    def test_oversized_history_and_wrong_timezone_fail_before_evaluation(self):
        strategy = load_strategy(write_strategy(self.root))
        for snapshot in (context((1, 2, 3, 4, 5)), context(timezone="UTC+03:00")):
            with self.subTest(snapshot=snapshot), self.assertRaises(DataError):
                strategy.evaluate(snapshot)

    def test_fill_callback_uses_copy_and_failure_does_not_commit(self):
        path = write_strategy(
            self.root,
            """def generate_signal(ctx, params):
    return long_decision(reason="test")
def on_fill(state, fill):
    state["last_fill"] = fill.id
    if fill.id == "failed":
        raise ValueError("Synthetic fill callback failure")
""",
        )
        strategy = load_strategy(path)
        state = {"last_fill": "previous"}
        fill = Fill("new", CUTOFF, "TEST", "BUY", 2, 10)
        self.assertEqual(strategy.apply_fill(state, fill), {"last_fill": "new"})
        with self.assertRaises(StrategyError):
            strategy.apply_fill(state, replace(fill, id="failed"))
        self.assertEqual(state, {"last_fill": "previous"})

    def test_invalid_strategy_and_invalid_quantities_are_not_flat_signals(self):
        path = self.root / "strategy.py"
        path.write_text("STRATEGY_METADATA = {}", encoding="utf-8")
        with self.assertRaises(StrategyLoadError):
            load_strategy(path)
        path = write_strategy(self.root, "def generate_signal(ctx, params):\n    return {}\n")
        with self.assertRaises(DecisionError):
            load_strategy(path).evaluate(context())
        path = write_strategy(
            self.root,
            "def generate_signal(ctx, params):\n"
            "    return long_decision(reason='test', contracts='0.5')\n",
        )
        with self.assertRaises(DecisionError):
            load_strategy(path).evaluate(context())

    def test_strategy_system_exit_is_contained_but_keyboard_interrupt_propagates(self):
        for exception in ("SystemExit", "KeyboardInterrupt"):
            path = write_strategy(
                self.root,
                f"def generate_signal(ctx, params):\n    raise {exception}()\n",
            )
            expected = StrategyError if exception == "SystemExit" else KeyboardInterrupt
            with self.subTest(exception=exception), self.assertRaises(expected):
                load_strategy(path).evaluate(context())
