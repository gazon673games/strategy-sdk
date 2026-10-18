"""Desired strategy outcomes; these objects never submit broker orders."""

from dataclasses import dataclass, field
from decimal import Decimal

from .errors import DataError, DecisionError
from .json_data import json_copy
from .numbers import decimal_value


@dataclass(frozen=True, slots=True)
class Decision:
    kind: str
    reason: str
    target: int | None = None
    contracts: Decimal | None = None
    features: dict = field(default_factory=dict)
    skip_unaffordable_add: bool = False

    def __post_init__(self) -> None:
        if self.kind not in {"TARGET", "HOLD", "SKIP"}:
            raise DecisionError("Decision kind must be TARGET, HOLD, or SKIP")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise DecisionError("Decision requires a reason code")
        if self.kind == "TARGET":
            if type(self.target) not in {int, float} or self.target not in {-1, 0, 1}:
                raise DecisionError("Target must be -1, 0, or 1")
            object.__setattr__(self, "target", int(self.target))
        elif self.target is not None or self.contracts is not None:
            raise DecisionError("HOLD and SKIP cannot declare a target or contracts")
        if type(self.skip_unaffordable_add) is not bool:
            raise DecisionError("skip_unaffordable_add must be boolean")
        if self.skip_unaffordable_add and (
            self.kind != "TARGET" or not self.target or self.contracts is None
        ):
            raise DecisionError("Skipping an unaffordable add requires an explicit sized target")
        try:
            if self.contracts is not None:
                contracts = decimal_value(self.contracts, "contracts")
                if contracts < 0 or (self.target == 0 and contracts != 0):
                    raise DecisionError(
                        "Target quantity must be nonnegative and zero for a flat target"
                    )
                if self.target and contracts == 0:
                    raise DecisionError("Zero-sized entry must be an explicit flat decision")
                object.__setattr__(self, "contracts", contracts)
            if not isinstance(self.features, dict):
                raise DecisionError("Features must be a dictionary")
            object.__setattr__(self, "features", json_copy(self.features))
        except DataError as error:
            raise DecisionError(str(error)) from error

    def as_dict(self) -> dict:
        result = {
            "kind": self.kind,
            "target": self.target,
            "contracts": str(self.contracts) if self.contracts is not None else None,
            "reason": self.reason,
            "features": json_copy(self.features),
        }
        if self.skip_unaffordable_add:
            result["skip_unaffordable_add"] = True
        return result


def long_decision(*, reason: str, contracts=None, features: dict | None = None) -> Decision:
    return Decision("TARGET", reason, 1, contracts, features if features is not None else {})


def short_decision(*, reason: str, contracts=None, features: dict | None = None) -> Decision:
    return Decision("TARGET", reason, -1, contracts, features if features is not None else {})


def flat_decision(*, reason: str, features: dict | None = None) -> Decision:
    return Decision("TARGET", reason, 0, Decimal(0), features if features is not None else {})


def hold_decision(*, reason: str, features: dict | None = None) -> Decision:
    return Decision("HOLD", reason, features=features if features is not None else {})


def skip_decision(*, reason: str, features: dict | None = None) -> Decision:
    return Decision("SKIP", reason, features=features if features is not None else {})
