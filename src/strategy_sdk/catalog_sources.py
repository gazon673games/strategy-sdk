"""Snapshots a configured flat directory of trusted SDK strategy modules."""

import ast
import hashlib
import importlib.abc
import importlib.util
import json
import re
import sys
from dataclasses import replace
from importlib import import_module
from uuid import uuid4

from .errors import StrategyLoadError as StrategyPluginError
from .metadata import StrategyMetadata

MAX_CATALOG_BYTES = 2 * 1024 * 1024
NAME_PATTERN = re.compile(r"[a-zA-Z_][a-zA-Z_0-9]*\Z")


def catalog_files(root):
    if not root.is_dir():
        raise StrategyPluginError(f"SDK catalog directory does not exist: {root}")
    files = {}
    size = 0
    for path in sorted(root.glob("*.py")):
        if not NAME_PATTERN.fullmatch(path.stem) or path.resolve().parent != root.resolve():
            raise StrategyPluginError(f"Invalid SDK catalog file: {path.name}")
        with path.open("rb") as stream:
            raw = stream.read(MAX_CATALOG_BYTES - size + 1)
        size += len(raw)
        files[path.stem] = raw.decode("utf-8-sig")
        if len(files) > 256 or size > MAX_CATALOG_BYTES:
            raise StrategyPluginError("SDK catalog exceeds the snapshot size limit")
    return files


def catalog_entries(files):
    entries = {}
    for registry in ("__init__", "_private_registry"):
        tree = ast.parse(files.get(registry, ""))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "ENTRIES" for target in node.targets
            ):
                declared = ast.literal_eval(node.value)
                if not isinstance(declared, dict):
                    raise StrategyPluginError("SDK ENTRIES must be a literal dictionary")
                entries.update(declared)
    if not isinstance(entries, dict):
        raise StrategyPluginError("SDK ENTRIES must be a literal dictionary")
    registered = set()
    for name, entry in entries.items():
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            raise StrategyPluginError("Invalid SDK catalog name")
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise StrategyPluginError(f"Invalid SDK catalog entry: {name}")
        module, defaults = entry
        if not isinstance(module, str) or module not in files or not isinstance(defaults, dict):
            raise StrategyPluginError(f"Invalid SDK catalog entry: {name}")
        registered.add(module)
    for name, source in files.items():
        if name.startswith("_") or name in registered:
            continue
        # Discovery reads declarations only; strategy code runs when selected.
        try:
            tree = ast.parse(source)
            declares_metadata = any(
                isinstance(node, (ast.Assign, ast.AnnAssign))
                and any(
                    isinstance(target, ast.Name) and target.id == "STRATEGY_METADATA"
                    for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
                )
                for node in tree.body
            )
        except SyntaxError:
            # Keep broken strategies visible so selection reports their errors.
            declares_metadata = True
        if declares_metadata:
            entries.setdefault(name, (name, {}))
    return entries


def catalog_snapshot(root, name):
    files = catalog_files(root)
    return snapshot_from_files(files, name)


def snapshot_from_files(files, name):
    entries = catalog_entries(files)
    if name not in entries:
        raise StrategyPluginError(f"SDK catalog strategy not found: {name}")
    module, defaults = entries[name]
    needed = {}
    pending = [module]
    while pending:
        current = pending.pop()
        if current in needed:
            continue
        needed[current] = files[current]
        for node in ast.walk(ast.parse(files[current])):
            if isinstance(node, ast.ImportFrom):
                imported = node.module or ""
                if imported == "strategy_sdk.catalog" or (node.level and not imported):
                    dependencies = [alias.name for alias in node.names]
                elif imported.startswith("strategy_sdk.catalog."):
                    dependencies = [imported.split(".")[2]]
                elif node.level:
                    dependencies = [imported.split(".")[0]]
                else:
                    continue
            elif isinstance(node, ast.Import):
                dependencies = [
                    alias.name.split(".")[2]
                    for alias in node.names
                    if alias.name.startswith("strategy_sdk.catalog.")
                ]
            else:
                continue
            pending.extend(dependency for dependency in dependencies if dependency in files)
    return {
        "name": name,
        "module": module,
        "defaults": defaults,
        "files": needed,
    }


class SnapshotImports(ast.NodeTransformer):
    def __init__(self, namespace):
        self.namespace = namespace

    def catalog_name(self, name):
        prefix = "strategy_sdk.catalog"
        return (
            self.namespace + name[len(prefix) :]
            if name == prefix or name.startswith(prefix + ".")
            else name
        )

    def visit_ImportFrom(self, node):
        if node.module:
            node.module = self.catalog_name(node.module)
        return node

    def visit_Import(self, node):
        for alias in node.names:
            mapped = self.catalog_name(alias.name)
            if mapped != alias.name and not alias.asname:
                raise StrategyPluginError(
                    "Catalog helper imports require 'from ... import ...' or an alias"
                )
            alias.name = mapped
        return node

    def visit_FunctionDef(self, node):
        for statement in ast.walk(node):
            if isinstance(statement, ast.ImportFrom):
                imported = statement.module or ""
                local_helper = statement.level or self.catalog_name(imported) != imported
            elif isinstance(statement, ast.Import):
                local_helper = any(
                    self.catalog_name(alias.name) != alias.name for alias in statement.names
                )
            else:
                continue
            if local_helper:
                raise StrategyPluginError("Import catalog helpers at module level before callbacks")
        return self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


class SnapshotModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, files, namespace):
        self.files = files
        self.namespace = namespace

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.namespace:
            return importlib.util.spec_from_loader(fullname, self, is_package=True)
        if fullname.startswith(self.namespace + ".") and fullname.rsplit(".", 1)[-1] in self.files:
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        if module.__name__ == self.namespace:
            return
        name = module.__name__.rsplit(".", 1)[-1]
        filename = f"<sdk-catalog/{name}.py>"
        tree = SnapshotImports(self.namespace).visit(ast.parse(self.files[name], filename))
        exec(compile(tree, filename, "exec"), module.__dict__)


def load_catalog_snapshot(snapshot):
    serialized = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()
    if len(serialized) > MAX_CATALOG_BYTES * 2:
        raise StrategyPluginError("SDK catalog snapshot is too large")
    namespace = "_strategy_sdk_catalog_" + uuid4().hex
    loader = SnapshotModules(snapshot["files"], namespace)
    sys.meta_path.insert(0, loader)
    try:
        module = import_module(namespace + "." + snapshot["module"])
        if not isinstance(getattr(module, "STRATEGY_METADATA", None), StrategyMetadata):
            raise StrategyPluginError("Catalog module must declare SDK STRATEGY_METADATA")
        module.STRATEGY_METADATA = replace(module.STRATEGY_METADATA, name=snapshot["name"])
        module.__strategy_source__ = hashlib.sha256(serialized).digest()
        module.__strategy_defaults__ = snapshot["defaults"]
        return module
    except (Exception, SystemExit) as error:
        raise StrategyPluginError(
            f"SDK catalog strategy failed to load: {snapshot['name']}: {error}"
        ) from error
    finally:
        sys.meta_path.remove(loader)
        for name in list(sys.modules):
            if name == namespace or name.startswith(namespace + "."):
                del sys.modules[name]


def load_file_strategy(path, params=None):
    """Pin a trusted file and its static catalog helpers, including standalone catalogs."""
    from pathlib import Path

    from .loading import strategy_from_module

    path = Path(path).resolve()
    files = catalog_files(path.parent)
    files["__init__"] = ""
    snapshot = snapshot_from_files(files, path.stem)
    module = load_catalog_snapshot(snapshot)
    return strategy_from_module(
        module, {**snapshot["defaults"], **(params or {})}, module.__strategy_source__.hex()
    )
