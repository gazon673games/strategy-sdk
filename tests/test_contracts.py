import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sdk_fixtures import CUTOFF, bars, context

from strategy_sdk import (
    Bar,
    DataError,
    Decision,
    DecisionError,
    Instrument,
    InsufficientHistory,
    Position,
    flat_decision,
    hold_decision,
    skip_decision,
)


class SnapshotTests(unittest.TestCase):
    def test_unfinished_duplicate_unsorted_and_overlapping_bars_are_rejected(self):
        original = context()
        for history in (
            original.bars + bars((14,), cutoff=CUTOFF + timedelta(minutes=5)),
            original.bars + (original.bars[-1],),
            tuple(reversed(original.bars)),
            (original.bars[0], replace(original.bars[1], opened_at=original.bars[0].opened_at)),
        ):
            with self.subTest(history=history), self.assertRaises(DataError):
                replace(original, bars=history)
        self.assertEqual(original.current_bar().closed_at, CUTOFF)

    def test_bad_ohlc_volume_nonfinite_prices_and_naive_clock_are_rejected(self):
        bar = bars((10,))[0]
        for change in (
            {"low": 11},
            {"close": "NaN"},
            {"volume": -1},
            {"open": True},
            {"closed_at": CUTOFF.replace(tzinfo=None)},
        ):
            with self.subTest(change=change), self.assertRaises(DataError):
                replace(bar, **change)
        with self.assertRaises(DataError):
            replace(context(), as_of=CUTOFF.replace(tzinfo=None))
        # Negative historical prices are valid OHLC, independent of sizing rules.
        self.assertEqual(bars((-5,))[0].close, Decimal(-5))

    def test_repeated_dst_hour_is_ordered_by_utc_and_cannot_leak_future_data(self):
        try:
            zone = ZoneInfo("America/New_York")
        except ZoneInfoNotFoundError:
            self.skipTest("Optional IANA timezone data is unavailable")
        opened = datetime(2026, 11, 1, 1, 55, tzinfo=zone, fold=0)
        closed = datetime(2026, 11, 1, 1, 0, tzinfo=zone, fold=1)
        bar = Bar(opened, closed, 10, 10, 10, 10)
        self.assertEqual(bar.closed_at - bar.opened_at, timedelta(minutes=5))
        earlier = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)
        with self.assertRaises(DataError):
            replace(context(), bars=(bar,), as_of=earlier)

    def test_offsets_and_session_boundaries_have_explicit_meaning(self):
        snapshot = context(timezone="UTC+03:00", position=Position("TEST", -40))
        self.assertEqual(snapshot.current_time.hour, 15)
        self.assertEqual(snapshot.previous_position, -1)
        self.assertEqual(snapshot.position_quantity, Decimal(-40))
        self.assertEqual(snapshot.value("close", offset=-1), Decimal(12))
        self.assertEqual(snapshot.series("ts")[0], snapshot.bars[0].opened_at)
        from datetime import time

        self.assertEqual(len(snapshot.session_history(time(14, 45))), 3)
        with self.assertRaises(DataError):
            snapshot.value("close", offset=1)
        with self.assertRaises(InsufficientHistory):
            snapshot.value("close", offset=-4)
        with self.assertRaises(DataError):
            replace(snapshot, position=Position("OTHER", 1))


class DecisionTests(unittest.TestCase):
    def test_flat_hold_and_skip_are_distinct_and_quantities_are_explicit(self):
        flat, hold, skip = (
            factory(reason="test") for factory in (flat_decision, hold_decision, skip_decision)
        )
        self.assertEqual((flat.kind, flat.target, flat.contracts), ("TARGET", 0, Decimal(0)))
        self.assertEqual((hold.kind, hold.target), ("HOLD", None))
        self.assertEqual((skip.kind, skip.target), ("SKIP", None))
        for kwargs in (
            {"target": True},
            {"target": []},
            {"target": 2},
            {"target": 0, "contracts": 1},
            {"target": 1, "contracts": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(DecisionError):
                Decision("TARGET", "test", **kwargs)

    def test_features_are_copied_and_serialized_output_cannot_change_decision(self):
        features = {"nested": {"count": 1}}
        decision = Decision("TARGET", "test", 1, "0.5", features)
        features["nested"]["count"] = 2
        encoded = decision.as_dict()
        encoded["features"]["nested"]["count"] = 3
        self.assertEqual(decision.features["nested"]["count"], 1)
        self.assertEqual(decision.as_dict()["contracts"], "0.5")
        with self.assertRaises(DataError):
            Instrument("TEST", "USD", quantity_step=0)
