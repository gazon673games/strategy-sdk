import json
import unittest

from sdk_fixtures import CUTOFF

from strategy_sdk import StateEnvelope, StateError

INSTANCE = "11111111-1111-4111-8111-111111111111"
REVISION = "a" * 64


class StateTests(unittest.TestCase):
    def test_roundtrip_is_independent_and_checks_identity_and_revision(self):
        source = {"quantity": "40", "nested": {"previous_signal": 1}}
        envelope = StateEnvelope(INSTANCE, REVISION, CUTOFF, source)
        source["nested"]["previous_signal"] = -1
        restored = StateEnvelope.from_json(envelope.to_json())
        state = restored.restore(INSTANCE, REVISION)
        state["nested"]["previous_signal"] = 0
        self.assertEqual(restored.data["nested"]["previous_signal"], 1)
        for identity, revision in (
            ("22222222-2222-4222-8222-222222222222", REVISION),
            (INSTANCE, "b" * 64),
        ):
            with self.subTest(identity=identity), self.assertRaises(StateError):
                restored.restore(identity, revision)

    def test_corrupt_nonfinite_future_schema_and_unknown_fields_are_rejected(self):
        raw = json.loads(StateEnvelope(INSTANCE, REVISION, CUTOFF, {}).to_json())
        for change in (
            {"sdk_api_version": 2},
            {"sdk_api_version": True},
            {"instance_id": "invalid"},
            {"extra": 1},
            {"data": {"value": float("nan")}},
            {"data": {"value": float("inf")}},
        ):
            with self.subTest(change=change), self.assertRaises(StateError):
                StateEnvelope.from_json(json.dumps({**raw, **change}))
        with self.assertRaises(StateError):
            StateEnvelope.from_json('{"data": {}, "data": {}}')
        with self.assertRaises(StateError):
            StateEnvelope.from_json("[1]")

    def test_limits_and_naive_timestamp_do_not_silently_reset_state(self):
        text = StateEnvelope(INSTANCE, REVISION, CUTOFF, {"value": 1}).to_json()
        with self.assertRaises(StateError):
            StateEnvelope.from_json(text, max_bytes=1)
        with self.assertRaises(StateError):
            StateEnvelope(INSTANCE, REVISION, CUTOFF.replace(tzinfo=None), {})
        with self.assertRaises(StateError):
            StateEnvelope(INSTANCE, REVISION, CUTOFF, {"value": object()})
