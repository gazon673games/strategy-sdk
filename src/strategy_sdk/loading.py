"""Load a trusted single-file Python strategy from one source snapshot.

The module may import installed packages. Relative/local sibling imports are not
resolved automatically. This loader is not a sandbox or a dependency installer.
"""

import hashlib
import sys
from pathlib import Path
from types import ModuleType
from uuid import uuid4

from .errors import StrategyError, StrategyLoadError
from .metadata import StrategyMetadata
from .runtime import Strategy


def load_strategy(path: str | Path, params=None) -> Strategy:
    path = Path(path).resolve()
    try:
        source = path.read_bytes()
        revision = hashlib.sha256(source).hexdigest()
        # A unique name isolates modules loaded concurrently with the same source.
        name = f"_strategy_sdk_{uuid4().hex}"
        module = ModuleType(name)
        module.__file__ = str(path)
        module.__package__ = ""
        sys.modules[name] = module
        try:
            exec(compile(source, str(path), "exec"), module.__dict__)
        finally:
            sys.modules.pop(name, None)
        return strategy_from_module(module, params, revision)
    except StrategyError:
        raise
    except (Exception, SystemExit) as error:
        raise StrategyLoadError("Trusted strategy module could not be loaded") from error


def strategy_from_module(module, params, revision):
    metadata = getattr(module, "STRATEGY_METADATA", None)
    if not isinstance(metadata, StrategyMetadata):
        raise StrategyLoadError("Module must declare STRATEGY_METADATA as StrategyMetadata")
    functions = {}
    for name in ("generate_signal", "data_requirements", "initialize", "on_fill"):
        function = getattr(module, name, None)
        if name in {"generate_signal", "data_requirements"} or function is not None:
            if not callable(function):
                raise StrategyLoadError(f"Strategy must declare callable {name}")
        functions[name] = function
    return Strategy(
        metadata,
        params,
        functions["data_requirements"],
        source_revision=revision,
        generate_signal=functions["generate_signal"],
        initialize=functions["initialize"],
        on_fill=functions["on_fill"],
    )
