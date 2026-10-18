"""Compile a validated visual preset using the existing SDK algorithm callbacks."""

import keyword
import os
import re
import tempfile
from importlib import import_module
from pathlib import Path

from strategy_sdk import ParameterError
from strategy_sdk.catalog import ENTRIES, load_catalog_strategy
from strategy_sdk.json_data import feature_snapshot

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src" / "strategy_sdk" / "catalog"
MODEL_KEYS = {"schema_version", "name", "version", "template", "params"}
NAME = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")


def catalog_schema():
    result = []
    for name, (module_name, overrides) in ENTRIES.items():
        module = import_module(f"strategy_sdk.catalog.{module_name}")
        specs = module.STRATEGY_METADATA.params
        defaults = {
            spec.name: overrides.get(spec.name, spec.default)
            if overrides.get(spec.name, spec.default) is not None
            else spec.default
            for spec in specs
        }
        strategy = load_catalog_strategy(name, defaults)
        result.append(
            {
                "name": name,
                "description": (module.__doc__ or "").strip(),
                "params": feature_snapshot(**strategy.parameters),
                "specs": [
                    feature_snapshot(
                        name=spec.name,
                        type=spec.param_type,
                        nullable=defaults[spec.name] is None and not spec.required,
                        min=spec.min_value,
                        max=spec.max_value,
                        choices=spec.choices,
                    )
                    for spec in specs
                ],
            }
        )
    return {"schema_version": 1, "templates": result}


def compile_model(raw):
    if not isinstance(raw, dict) or set(raw) != MODEL_KEYS:
        raise ParameterError("Model must contain schema_version, name, version, template, params")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ParameterError("Unsupported visual model version")
    name = raw["name"]
    if not isinstance(name, str) or not NAME.fullmatch(name) or keyword.iskeyword(name):
        raise ParameterError("Name must contain lowercase letters, digits and underscores")
    if name in ENTRIES:
        raise ParameterError("Choose a new name; an existing SDK strategy cannot be overwritten")
    version = raw["version"]
    if not isinstance(version, str) or not re.fullmatch(r"[a-zA-Z0-9_.]{1,40}", version):
        raise ParameterError("Version must contain 1 to 40 letters, digits, dots or underscores")
    template = raw["template"]
    if not isinstance(template, str) or template not in ENTRIES:
        raise ParameterError("Unknown SDK template")
    params = raw["params"]
    if not isinstance(params, dict):
        raise ParameterError("Parameters must be an object")
    module_name = ENTRIES[template][0]
    module = import_module(f"strategy_sdk.catalog.{module_name}")
    if set(params) != {spec.name for spec in module.STRATEGY_METADATA.params}:
        raise ParameterError("All template parameters must be present exactly once")
    for spec in module.STRATEGY_METADATA.params:
        if params[spec.name] is None and (spec.default is not None or spec.required):
            raise ParameterError(f"{spec.name} cannot be null in the editor")
    strategy = load_catalog_strategy(template, params)
    normalized = feature_snapshot(**strategy.parameters)
    for spec in module.STRATEGY_METADATA.params:
        if spec.param_type == "int" and normalized[spec.name] is not None:
            if abs(normalized[spec.name]) > 2**53 - 1:
                raise ParameterError("Editor integers must fit the JavaScript safe integer range")
    model = {**raw, "params": normalized}
    callbacks = ["data_requirements", "generate_signal"]
    callbacks.extend(key for key in ("initialize", "on_fill") if hasattr(module, key))
    strict_crossover = template == "moving_average_crossover"
    aliases = {name: name for name in callbacks}
    if strict_crossover:
        aliases["data_requirements"] = "_base_requirements"
    imports = "\n".join(f"    {key} as {alias}," for key, alias in aliases.items())
    constraints = ""
    if strict_crossover:
        constraints = (
            "\n\ndef data_requirements(params):\n"
            "    if params['fast_window'] >= params['slow_window']:\n"
            "        raise ParameterError('Crossover requires fast_window < slow_window')\n"
            "    return _base_requirements(params)\n"
        )
    defaults = "\n".join(f"    {key!r}: {value!r}," for key, value in sorted(normalized.items()))
    extra_import = "from strategy_sdk import ParameterError\n" if strict_crossover else ""
    source = (
        '"""Visual SDK preset. Edit its JSON project in the strategy editor."""\n\n'
        "from dataclasses import replace\n\n"
        f"{extra_import}from strategy_sdk.catalog.{module_name} import (\n"
        "    STRATEGY_METADATA as _BASE_METADATA,\n"
        f"{imports}\n)\n\n"
        f"_DEFAULTS = {{\n{defaults}\n}}\n\n"
        "STRATEGY_METADATA = replace(\n"
        f"    _BASE_METADATA,\n    name={name!r},\n    version={version!r},\n"
        "    params=tuple(\n"
        "        replace(spec, default=_DEFAULTS[spec.name]) for spec in _BASE_METADATA.params\n"
        "    ),\n"
        ")\n" + constraints
    )
    compile(source, f"{name}.py", "exec")
    return {"model": model, "python": source, "requirements": strategy.requirements.as_dict()}


def publish_model(raw, target=CATALOG):
    result = compile_model(raw)
    target = Path(target).resolve()
    path = target / f"{result['model']['name']}.py"
    # Publish complete content atomically. A catalog reader never sees half a Python file.
    with tempfile.TemporaryDirectory(dir=target, prefix=".visual-") as staging:
        temporary = Path(staging) / "strategy.tmp"
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(result["python"])
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Fails if destination exists, including a concurrent publish.
    return {"filename": path.name, "path": str(path)}
