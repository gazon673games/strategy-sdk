"""Catalog infrastructure with a blank, non-trading callback."""

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from importlib import import_module
from importlib.resources import files

from strategy_sdk._version import __version__
from strategy_sdk.errors import ParameterError
from strategy_sdk.runtime import Strategy

ENTRIES = {"empty": ("empty", {})}
DEPENDENCIES = {}
_load_local = None

# Optional local modules are excluded from Git and distribution archives.
try:
    from ._private_registry import DEPENDENCIES as _LOCAL_DEPENDENCIES
    from ._private_registry import ENTRIES as _LOCAL_ENTRIES
    from ._private_registry import load_catalog_strategy as _load_local
except ModuleNotFoundError as error:
    if error.name != __name__ + "._private_registry":
        raise
else:
    ENTRIES.update(_LOCAL_ENTRIES)
    DEPENDENCIES.update(
        {
            module: ("_common", *_LOCAL_DEPENDENCIES.get(module, ()))
            for module, _ in _LOCAL_ENTRIES.values()
        }
    )


def list_strategies() -> tuple[str, ...]:
    return tuple(sorted(ENTRIES))


def load_catalog_strategy(name: str, params: Mapping | None = None) -> Strategy:
    if _load_local is not None and name in _LOCAL_ENTRIES:
        return _load_local(name, params)
    if not isinstance(name, str) or name not in ENTRIES:
        raise ParameterError("Unknown catalog strategy; configure a local source file")
    if params is not None and not isinstance(params, Mapping):
        raise ParameterError("Strategy parameters must be a mapping")
    module_name, defaults = ENTRIES[name]
    module = import_module(f"strategy_sdk.catalog.{module_name}")
    digest = hashlib.sha256(__version__.encode())
    resources = files("strategy_sdk.catalog")
    for dependency in (module_name, *DEPENDENCIES.get(module_name, ())):
        digest.update(dependency.encode())
        digest.update(resources.joinpath(f"{dependency}.py").read_bytes())
    return Strategy(
        replace(module.STRATEGY_METADATA, name=name),
        {**defaults, **(params or {})},
        module.data_requirements,
        source_revision=digest.hexdigest(),
        generate_signal=module.generate_signal,
        initialize=getattr(module, "initialize", None),
        on_fill=getattr(module, "on_fill", None),
    )


__all__ = ["list_strategies", "load_catalog_strategy"]
