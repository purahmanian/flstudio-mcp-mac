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


def mock_bridge_enabled() -> bool:
    return os.getenv("FLSTUDIO_MCP_BRIDGE", "").strip().lower() in {"mock", "test"}


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


class MockBridge:
    """Deterministic bridge used for MCP protocol tests without FL Studio."""

    def __init__(self) -> None:
        self.tempo = 120.0
        self.playing = False
        self.recording = False
        self.loop_mode = 1
        self.selected_channel = 0
        self.tracks = [
            {
                "index": 0,
                "name": "Master",
                "volume": 1.0,
                "volume_db": 0.0,
                "pan": 0.0,
                "muted": False,
                "solo": False,
                "selected": True,
            },
            {
                "index": 1,
                "name": "Insert 1",
                "volume": 0.8,
                "volume_db": -3.0,
                "pan": 0.0,
                "muted": False,
                "solo": False,
                "selected": False,
            },
        ]
        self.channels = [
            {
                "index": 0,
                "name": "Sampler",
                "volume": 0.8,
                "pan": 0.0,
                "muted": False,
                "solo": False,
                "selected": True,
                "target_mixer_track": 1,
            },
            {
                "index": 1,
                "name": "Keys",
                "volume": 0.75,
                "pan": 0.0,
                "muted": False,
                "solo": False,
                "selected": False,
                "target_mixer_track": 1,
            },
        ]

    @property
    def connected(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def call(self, command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        if command == "get_status":
            return self._status()
        if command == "transport":
            return self._transport(str(params.get("action", "")))
        if command == "set_tempo":
            self.tempo = float(params["bpm"])
            return self._status()
        if command == "mixer_tracks":
            limit = int(params.get("limit", 32))
            return {"tracks": self.tracks[:limit], "count": len(self.tracks)}
        if command == "set_mixer_track":
            return {"track": self._set_item(self.tracks, params)}
        if command == "channels":
            limit = int(params.get("limit", 64))
            return {"channels": self.channels[:limit], "count": len(self.channels)}
        if command == "set_channel":
            item = self._set_item(self.channels, params)
            if params.get("selected") is True:
                self._select_channel(int(params["index"]))
            return {"channel": item}
        raise BridgeError(f"unknown command: {command}")

    def _status(self) -> dict[str, Any]:
        return {
            "mock": True,
            "version": "mock",
            "tempo": self.tempo,
            "playing": self.playing,
            "recording": self.recording,
            "loop_mode": self.loop_mode,
            "song_pos": 0,
            "song_length": 0,
            "selected_channel": self.selected_channel,
            "active_pattern": 1,
            "mixer_track_count": len(self.tracks),
        }

    def _transport(self, action: str) -> dict[str, Any]:
        if action == "play":
            self.playing = True
        elif action == "stop":
            self.playing = False
        elif action == "record_toggle":
            self.recording = not self.recording
        elif action == "rewind":
            pass
        elif action == "song_mode":
            self.loop_mode = 1
        elif action == "pattern_mode":
            self.loop_mode = 0
        elif action == "metronome_toggle":
            pass
        else:
            raise BridgeError(f"unsupported transport action: {action}")
        return self._status()

    def _set_item(self, items: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
        index = int(params["index"])
        try:
            item = items[index]
        except IndexError as exc:
            raise BridgeError(f"index out of range: {index}") from exc
        for key in ("volume", "pan", "muted", "solo", "name", "selected"):
            if key in params:
                item[key] = params[key]
        return item

    def _select_channel(self, index: int) -> None:
        self.selected_channel = index
        for channel in self.channels:
            channel["selected"] = channel["index"] == index


_bridge: MidiBridge | MockBridge | None = None


def get_bridge() -> MidiBridge | MockBridge:
    global _bridge
    if _bridge is None:
        _bridge = MockBridge() if mock_bridge_enabled() else MidiBridge()
    return _bridge


def reset_bridge() -> None:
    global _bridge
    if _bridge is not None:
        _bridge.close()
    _bridge = None
