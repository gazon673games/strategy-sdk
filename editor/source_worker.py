"""Offline contract validation in a disposable, time-limited editor subprocess."""

import json
import sys

from editor.compiler import CATALOG
from strategy_sdk.catalog_sources import catalog_files, load_catalog_snapshot, snapshot_from_files
from strategy_sdk.json_data import feature_snapshot
from strategy_sdk.loading import strategy_from_module


def main():
    payload = json.loads(sys.stdin.read())
    files = catalog_files(CATALOG)
    files["__init__"] = ""
    name = payload["filename"].removesuffix(".py")
    files[name] = payload["source"]
    snapshot = snapshot_from_files(files, name)
    module = load_catalog_snapshot(snapshot)
    strategy = strategy_from_module(
        module, payload.get("params", {}), module.__strategy_source__.hex()
    )
    strategy.initial_state()
    result = {
        "name": strategy.metadata.name,
        "requirements": strategy.requirements.as_dict(),
        "params": feature_snapshot(**strategy.parameters),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (Exception, SystemExit) as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"[:1200]}))
        sys.exit(1)
