"""CoreMIDI bridge used by the MCP tools."""

from __future__ import annotations

import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

from .protocol import DEFAULT_CHANNEL, FrameDecoder, ProtocolError, encode_payload

DEFAULT_REQUEST_PORT = "FLStudioMCP Request"
DEFAULT_RESPONSE_PORT = "FLStudioMCP Response"
DEFAULT_TIMEOUT_SECONDS = 8.0


class BridgeError(RuntimeError):
    """Base error for bridge failures."""


class BridgeDependencyError(BridgeError):
    """Raised when python-rtmidi is not installed."""


class BridgeTimeoutError(BridgeError):
    """Raised when FL Studio does not respond before the deadline."""


@dataclass(frozen=True)
class BridgeConfig:
    request_port: str = DEFAULT_REQUEST_PORT
    response_port: str = DEFAULT_RESPONSE_PORT
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    channel: int = DEFAULT_CHANNEL

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        return cls(
            request_port=os.getenv("FLSTUDIO_MCP_REQUEST_PORT", DEFAULT_REQUEST_PORT),
            response_port=os.getenv("FLSTUDIO_MCP_RESPONSE_PORT", DEFAULT_RESPONSE_PORT),
            timeout_seconds=float(os.getenv("FLSTUDIO_MCP_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)),
            channel=int(os.getenv("FLSTUDIO_MCP_CHANNEL", DEFAULT_CHANNEL)),
        )


class MidiBridge:
    """Half-duplex request/response bridge over virtual CoreMIDI ports."""

    def __init__(self, config: BridgeConfig | None = None) -> None:
        self.config = config or BridgeConfig.from_env()
        self._decoder = FrameDecoder(channel=self.config.channel)
        self._responses: dict[str, queue.Queue[dict[str, Any]]] = {}
        self._responses_lock = threading.Lock()
        self._midi_in: Any | None = None
        self._midi_out: Any | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        if self._connected:
            return

        try:
            import rtmidi  # type: ignore[import-not-found]
        except ImportError as exc:
            raise BridgeDependencyError(
                "python-rtmidi is required for the live FL Studio bridge. "
                "Install with `pip install python-rtmidi`."
            ) from exc

        midi_in = rtmidi.MidiIn()
        midi_out = rtmidi.MidiOut()
        midi_in.ignore_types(sysex=False, timing=True, active_sense=True)
        midi_in.open_virtual_port(self.config.response_port)
        midi_out.open_virtual_port(self.config.request_port)
        midi_in.set_callback(self._on_midi)

        self._midi_in = midi_in
        self._midi_out = midi_out
        self._connected = True

    def close(self) -> None:
        if self._midi_in is not None:
            self._midi_in.close_port()
        if self._midi_out is not None:
            self._midi_out.close_port()
        self._midi_in = None
        self._midi_out = None
        self._connected = False

    def call(self, command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.connect()
        assert self._midi_out is not None

        request_id = uuid.uuid4().hex
        response_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
        with self._responses_lock:
            self._responses[request_id] = response_queue

        payload = {
            "id": request_id,
            "command": command,
            "params": params or {},
        }

        try:
            for message in encode_payload(payload, channel=self.config.channel):
                self._midi_out.send_message(message)
                time.sleep(0.0008)

            try:
                response = response_queue.get(timeout=self.config.timeout_seconds)
            except queue.Empty as exc:
                raise BridgeTimeoutError(
                    f"FL Studio did not respond to `{command}` within "
                    f"{self.config.timeout_seconds:.1f}s"
                ) from exc
        finally:
            with self._responses_lock:
                self._responses.pop(request_id, None)

        if not response.get("ok", False):
            raise BridgeError(str(response.get("error", "FL Studio command failed")))
        result = response.get("result", {})
        if not isinstance(result, dict):
            return {"value": result}
        return result

    def _on_midi(self, event: tuple[list[int], float], _data: Any = None) -> None:
        message, _delta = event
        try:
            payload = self._decoder.feed(message)
        except ProtocolError:
            return
        if payload is None:
            return

        request_id = payload.get("id")
        if not isinstance(request_id, str):
            return
        with self._responses_lock:
            response_queue = self._responses.get(request_id)
        if response_queue is None:
            return
        try:
            response_queue.put_nowait(payload)
        except queue.Full:
            pass


_bridge: MidiBridge | None = None


def get_bridge() -> MidiBridge:
    global _bridge
    if _bridge is None:
        _bridge = MidiBridge()
    return _bridge

