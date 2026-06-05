"""Singleton CoreMIDI daemon for FL Studio MCP clients."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socketserver
import threading
from pathlib import Path
from typing import Any

from .bridge import BridgeError, MidiBridge, daemon_socket_path

MAX_REQUEST_BYTES = 1024 * 1024


class _BridgeRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline(MAX_REQUEST_BYTES + 1)
        if not line:
            return
        if len(line) > MAX_REQUEST_BYTES:
            self._send({"ok": False, "error": "request too large"})
            return

        try:
            request = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            self._send({"ok": False, "error": "invalid JSON request"})
            return

        if not isinstance(request, dict):
            self._send({"ok": False, "error": "request must be a JSON object"})
            return

        command = request.get("command")
        params = request.get("params", {})
        if not isinstance(command, str) or not command:
            self._send({"ok": False, "error": "command must be a non-empty string"})
            return
        if not isinstance(params, dict):
            self._send({"ok": False, "error": "params must be a JSON object"})
            return

        daemon = self.server.bridge_daemon
        try:
            with daemon.call_lock:
                result = daemon.bridge.call(command, params)
        except BridgeError as exc:
            self._send({"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 - daemon boundary
            self._send({"ok": False, "error": f"daemon command failed: {exc}"})
            return

        self._send({"ok": True, "result": result})

    def _send(self, payload: dict[str, Any]) -> None:
        self.wfile.write(json.dumps(payload).encode("utf-8") + b"\n")


class _BridgeUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, socket_path: str, bridge_daemon: BridgeDaemon) -> None:
        self.bridge_daemon = bridge_daemon
        super().__init__(socket_path, _BridgeRequestHandler)


class BridgeDaemon:
    def __init__(self, socket_path: Path | None = None, bridge: Any | None = None) -> None:
        self.socket_path = socket_path or daemon_socket_path()
        self.bridge = bridge or MidiBridge()
        self.call_lock = threading.Lock()
        self._server: _BridgeUnixServer | None = None

    def serve_forever(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()

        connect = getattr(self.bridge, "connect", None)
        if callable(connect):
            connect()

        server = _BridgeUnixServer(str(self.socket_path), self)
        self._server = server
        try:
            os.chmod(self.socket_path, 0o600)
            server.serve_forever()
        finally:
            server.server_close()
            self.bridge.close()
            self._server = None
            try:
                if self.socket_path.exists():
                    self.socket_path.unlink()
            except OSError:
                pass

    def shutdown(self) -> None:
        if self._server is not None:
            self._server.shutdown()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the FL Studio MCP MIDI daemon.")
    parser.add_argument(
        "--socket",
        type=Path,
        default=None,
        help="Unix socket path. Defaults to FLSTUDIO_MCP_DAEMON_SOCKET or the user app dir.",
    )
    args = parser.parse_args(argv)

    daemon = BridgeDaemon(socket_path=args.socket)

    def request_shutdown(_signum: int, _frame: Any) -> None:
        threading.Thread(target=daemon.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    daemon.serve_forever()


if __name__ == "__main__":
    main()
