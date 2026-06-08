import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_kafka_check: Callable[[], None] | None = None
_db_check: Callable[[], None] | None = None


def configure(
    kafka_check: Callable[[], None] | None = None,
    db_check: Callable[[], None] | None = None,
) -> None:
    global _kafka_check, _db_check
    _kafka_check = kafka_check
    _db_check = db_check


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        elif self.path == "/ready":
            errors: list[str] = []
            for name, check in [("kafka", _kafka_check), ("db", _db_check)]:
                if check is None:
                    continue
                try:
                    check()
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
            if errors:
                self._respond(503, {"status": "not ready", "errors": errors})
            else:
                self._respond(200, {"status": "ready"})
        else:
            self._respond(404, {"status": "not found"})

    def _respond(self, code: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # silence per-request access logs


def start_health_server(port: int = 8080) -> None:
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("health_server_started", port=port)
