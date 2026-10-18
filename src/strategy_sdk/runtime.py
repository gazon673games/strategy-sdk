"""Evaluate one configured strategy against a host-supplied snapshot."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import localcontext
from types import MappingProxyType

from ._version import SDK_API_VERSION
from .context import StrategyContext
from .decisions import Decision, flat_decision, skip_decision
from .errors import DataError, DecisionError, InsufficientHistory, StrategyError
from .json_data import feature_snapshot, json_copy
from .metadata import DataRequirements, StrategyMetadata
from .models import Fill
from .numbers import ARITHMETIC_CONTEXT
from .parameters import validate_strategy_params


@dataclass(frozen=True, slots=True)
class Evaluation:
    decision: Decision
    state: dict
    revision: str


class Strategy:
    """A pinned module and parameter snapshot. State is never kept on this object."""

    def __init__(
        self,
        metadata: StrategyMetadata,
        params,
        requirements: DataRequirements | Callable[[dict], DataRequirements],
        *,
        source_revision: str,
        generate_signal,
        initialize=None,
        on_fill=None,
    ):
        self.metadata = metadata
        self.parameters = MappingProxyType(validate_strategy_params(params, metadata.params))
        if callable(requirements):
            requirements = requirements(dict(self.parameters))
        if not isinstance(requirements, DataRequirements):
            raise DataError("Strategy must declare DataRequirements")
        self.requirements = requirements
        payload = {
            "source": source_revision,
            "sdk_api_version": SDK_API_VERSION,
            "name": metadata.name,
            "version": metadata.version,
            "params": feature_snapshot(**self.parameters),
            "requirements": requirements.as_dict(),
        }
        self.revision = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self._generate_signal = generate_signal
        self._initialize = initialize
        self._on_fill = on_fill

    def initial_state(self) -> dict:
        try:
            state = self._initialize(dict(self.parameters)) if self._initialize else {}
            if state is None:
                state = {}
            if not isinstance(state, dict):
                raise DataError("Initialize must return a state dictionary or None")
            return json_copy(state)
        except StrategyError:
            raise
        except (Exception, SystemExit) as error:
            raise StrategyError("Strategy initialization failed") from error

    def evaluate(self, context: StrategyContext) -> Evaluation:
        if not isinstance(context, StrategyContext):
            raise DataError("Evaluation requires a StrategyContext")
        requirements = self.requirements
        if context.timeframe != requirements.timeframe or context.timezone != requirements.timezone:
            raise DataError("Context timeframe or timezone does not match strategy requirements")
        if len(context.bars) > requirements.history_bars:
            raise DataError("Host supplied more history than the strategy declared")
        if context.state is not None and not isinstance(context.state, dict):
            raise DataError("Strategy state must be a dictionary")
        state = self.initial_state() if context.state is None else json_copy(context.state)
        context = replace(context, state=state)
        bar_count = len(context.bars)
        missing_history = bar_count < requirements.warmup_bars
        counts = {"bars": bar_count, "required_bars": requirements.warmup_bars}
        if requirements.minimum_session_bars:
            session_count = len(context.session_history(requirements.session_start))
            if session_count < requirements.minimum_session_bars:
                missing_history = True
            counts.update(
                session_bars=session_count,
                required_session_bars=requirements.minimum_session_bars,
            )
        if missing_history:
            if requirements.insufficient_history == "error":
                raise InsufficientHistory("Snapshot does not satisfy declared history requirements")
            factory = (
                flat_decision if requirements.insufficient_history == "flat" else skip_decision
            )
            return Evaluation(
                factory(reason="insufficient_history", features=counts), state, self.revision
            )
        try:
            decision = self._generate_signal(context, dict(self.parameters))
            if not isinstance(decision, Decision):
                raise DecisionError("generate_signal must return a Decision")
            # Validate again if trusted plugin code mutated a decision's nested features.
            decision = replace(decision)
            if decision.contracts is not None:
                with localcontext(ARITHMETIC_CONTEXT):
                    target = decision.contracts * decision.target
                    # A base-coin fee can leave an off-step holding. Orders still use
                    # the venue step, but an absolute target can preserve that dust.
                    quantity = (
                        abs(target - context.position_quantity)
                        if target * context.position_quantity > 0
                        else decision.contracts
                    )
                    if quantity % context.instrument.quantity_step:
                        raise DecisionError("Position change must be a multiple of quantity_step")
            return Evaluation(decision, json_copy(context.state), self.revision)
        except StrategyError:
            raise
        except (Exception, SystemExit) as error:
            raise StrategyError("Strategy evaluation failed") from error

    def apply_fill(self, state: dict, fill: Fill) -> dict:
        if not isinstance(state, dict) or not isinstance(fill, Fill):
            raise DataError("Fill callback requires a state dictionary and Fill")
        candidate = json_copy(state)
        if self._on_fill is None:
            return candidate
        try:
            self._on_fill(candidate, fill)
            return json_copy(candidate)
        except StrategyError:
            raise
        except (Exception, SystemExit) as error:
            raise StrategyError("Strategy fill callback failed") from error
