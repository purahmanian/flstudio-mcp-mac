from __future__ import annotations

import threading
import tempfile
import time
from pathlib import Path

import pytest

from flstudio_mcp_mac.bridge import (
    BridgeConfig,
    BridgeError,
    DaemonBridge,
    MockBridge,
    get_bridge,
    reset_bridge,
)
from flstudio_mcp_mac.daemon import BridgeDaemon


def _start_mock_daemon(socket_path: Path) -> tuple[BridgeDaemon, threading.Thread, DaemonBridge]:
    daemon = BridgeDaemon(socket_path=socket_path, bridge=MockBridge())
    thread = threading.Thread(target=daemon.serve_forever, daemon=True)
    thread.start()

    client = DaemonBridge(
        config=BridgeConfig(timeout_seconds=1.0),
        socket_path=socket_path,
        autostart=False,
    )

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if client.connected:
            return daemon, thread, client
        time.sleep(0.01)

    daemon.shutdown()
    raise AssertionError("mock daemon did not start")


def _short_socket_path() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="flmcp-", dir="/tmp")


def test_daemon_bridge_round_trip():
    socket_dir = _short_socket_path()
    with socket_dir as directory:
        daemon, thread, client = _start_mock_daemon(Path(directory) / "bridge.sock")
        try:
            assert client.call("get_status")["tempo"] == 120.0
            assert client.call("set_tempo", {"bpm": 128})["tempo"] == 128.0
            assert client.call("transport", {"action": "play"})["playing"] is True
        finally:
            daemon.shutdown()
            thread.join(timeout=2)


def test_daemon_bridge_surfaces_bridge_errors():
    socket_dir = _short_socket_path()
    with socket_dir as directory:
        daemon, thread, client = _start_mock_daemon(Path(directory) / "bridge.sock")
        try:
            with pytest.raises(BridgeError, match="unknown command"):
                client.call("render_project")
        finally:
            daemon.shutdown()
            thread.join(timeout=2)


def test_daemon_bridge_without_autostart_reports_unreachable():
    socket_dir = _short_socket_path()
    with socket_dir as directory:
        client = DaemonBridge(
            config=BridgeConfig(timeout_seconds=1.0),
            socket_path=Path(directory) / "missing.sock",
            autostart=False,
        )

        with pytest.raises(BridgeError, match="not reachable"):
            client.call("get_status")


def test_default_bridge_mode_is_daemon(monkeypatch: pytest.MonkeyPatch):
    socket_dir = _short_socket_path()
    with socket_dir as directory:
        monkeypatch.delenv("FLSTUDIO_MCP_BRIDGE", raising=False)
        monkeypatch.setenv("FLSTUDIO_MCP_DAEMON_SOCKET", str(Path(directory) / "bridge.sock"))
        reset_bridge()
        try:
            assert isinstance(get_bridge(), DaemonBridge)
        finally:
            reset_bridge()
