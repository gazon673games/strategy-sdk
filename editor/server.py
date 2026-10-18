"""Loopback editor for visual presets and explicitly trusted Python strategies."""

import json
import mimetypes
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from editor.compiler import CATALOG, catalog_schema, compile_model, publish_model
from editor.source_editor import list_sources, open_source, store_source, validate_source
from strategy_sdk import StrategyError
from strategy_sdk.source_files import SourceConflict

DIST = Path(__file__).resolve().parent / "dist"
MAX_BODY = 64 * 1024


class EditorServer(ThreadingHTTPServer):
    request_queue_size = 32

    def __init__(self, port=8765):
        self.token = secrets.token_urlsafe(32)
        self.schema = catalog_schema()
        super().__init__(("127.0.0.1", port), EditorHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"


class EditorHandler(BaseHTTPRequestHandler):
    timeout = 5

    def log_message(self, format, *args):
        pass

    def respond(self, status, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def trusted_request(self, write=False):
        if self.headers.get("Host") != self.server.origin.removeprefix("http://"):
            self.respond(403, {"error": "Use the loopback editor URL"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin != self.server.origin:
            self.respond(403, {"error": "Foreign origins are forbidden"})
            return False
        if write and (
            origin != self.server.origin or self.headers.get("X-Editor-Token") != self.server.token
        ):
            self.respond(403, {"error": "Editor session authorization is required"})
            return False
        return True

    def do_GET(self):
        if not self.trusted_request():
            return
        route = urlsplit(self.path).path
        if route == "/api/catalog":
            self.respond(200, {**self.server.schema, "token": self.server.token})
            return
        if route == "/api/sources":
            self.respond(200, list_sources())
            return
        relative = route.lstrip("/") or "index.html"
        path = (DIST / relative).resolve()
        if not path.is_relative_to(DIST.resolve()) or not path.is_file():
            self.respond(404, {"error": "File not found"})
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            content_type = "text/javascript"
        self.respond(200, path.read_bytes(), content_type)

    def do_POST(self):
        if not self.trusted_request(write=True):
            return
        handlers = {
            "/api/compile": compile_model,
            "/api/publish": publish_model,
            "/api/source/open": open_source,
            "/api/source/validate": validate_source,
            "/api/source/save": store_source,
        }
        handler = handlers.get(self.path)
        if handler is None:
            self.respond(404, {"error": "Unknown endpoint"})
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.respond(415, {"error": "JSON is required"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            maximum = 512 * 1024 if self.path.startswith("/api/source/") else MAX_BODY
            if not 0 < size <= maximum:
                if 0 < size <= 512 * 1024:
                    # Drain small rejected bodies before closing the connection.
                    self.rfile.read(size)
                self.respond(413, {"error": f"Request must fit {maximum // 1024} KiB"})
                return
            raw = self.rfile.read(size)
            model = json.loads(raw, parse_constant=reject_constant)
            result = handler(model)
            if handler is compile_model:
                path = CATALOG / f"{result['model']['name']}.py"
                result["catalog_file_exists"] = path.exists()
            self.respond(200, result)
        except SourceConflict as error:
            self.respond(409, {"error": str(error)})
        except FileExistsError:
            self.respond(409, {"error": "File already exists; choose another name"})
        except (
            ValueError,
            SyntaxError,
            StrategyError,
            TypeError,
            KeyError,
            RecursionError,
        ) as error:
            self.respond(400, {"error": str(error) or "Invalid project"})
        except TimeoutError:
            self.respond(408, {"error": "Request timed out"})
        except OSError:
            self.respond(500, {"error": "Cannot read or write editor files"})


def reject_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")
