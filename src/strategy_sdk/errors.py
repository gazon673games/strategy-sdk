"""Errors that hosts can classify without parsing messages."""


class StrategyError(Exception):
    """Base error for the public SDK contract."""


class DataError(StrategyError):
    """The supplied market or account snapshot is invalid."""


class InsufficientHistory(DataError):
    """Valid history does not satisfy the strategy's declared requirements."""


class ParameterError(StrategyError):
    """A strategy parameter or its declaration is invalid."""


class DecisionError(StrategyError):
    """A strategy returned an invalid decision."""


class StateError(StrategyError):
    """State cannot be decoded or belongs to another instance or revision."""


class StrategyLoadError(StrategyError):
    """A trusted strategy module cannot be loaded."""
