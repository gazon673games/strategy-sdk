"""Run the optional visual editor from a source checkout using only stdlib Python."""

import argparse
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from editor.server import DIST, EditorServer  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Local Blockly / LiteGraph strategy editor")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the default browser")
    args = parser.parse_args()
    if not (DIST / "index.html").is_file():
        parser.error("Build the frontend first: cd editor && npm ci && npm run build")
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535")
    with EditorServer(args.port) as server:
        print(f"Strategy editor: {server.origin}", flush=True)
        if args.open:
            webbrowser.open(server.origin)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nEditor stopped.")


if __name__ == "__main__":
    main()
