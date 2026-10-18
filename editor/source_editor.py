"""Python source endpoints. Only explicitly requested validation executes trusted code."""

import json
import os
import subprocess
import sys

from editor.compiler import CATALOG, ROOT
from strategy_sdk.catalog_sources import catalog_entries, catalog_files
from strategy_sdk.source_files import read_source, save_source, source_path


def list_sources():
    entries = catalog_entries(catalog_files(CATALOG))
    return {"files": sorted({module + ".py" for module, _ in entries.values()})}


def open_source(payload):
    return read_source(CATALOG, payload["filename"])


def validate_source(payload):
    source_path(CATALOG, payload["filename"])
    if not isinstance(payload.get("source"), str) or len(payload["source"].encode()) > 256 * 1024:
        raise ValueError("Source must fit 256 KiB")
    compile(payload["source"], payload["filename"], "exec")
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment["PYTHONPATH"] = str(ROOT / "src")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "editor.source_worker"],
            cwd=ROOT,
            env=environment,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        raise ValueError("Strategy validation exceeded five seconds") from None
    try:
        checked = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise ValueError("Strategy must not print during module loading") from None
    if result.returncode:
        raise ValueError(checked.get("error", "SDK contract validation failed"))
    return checked


def store_source(payload):
    checked = validate_source(payload)
    saved = save_source(CATALOG, payload["filename"], payload["source"], payload.get("revision"))
    return {**saved, **checked}
