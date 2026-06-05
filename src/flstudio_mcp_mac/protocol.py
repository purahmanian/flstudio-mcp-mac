"""Small JSON-over-MIDI control-change protocol.

FL Studio's MIDI scripting API reliably handles short MIDI messages, so this
bridge sends base64-encoded JSON one character at a time over control-change
messages. It is intentionally boring and half-duplex: one command, one response.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

MIDI_CONTROL_CHANGE = 0xB0
DEFAULT_CHANNEL = 15
CC_START = 120
CC_DATA = 121
CC_END = 122


class ProtocolError(ValueError):
    """Raised when an incoming MIDI frame cannot be decoded."""


def encode_payload(payload: dict[str, Any], channel: int = DEFAULT_CHANNEL) -> list[list[int]]:
    """Encode a JSON payload into MIDI CC messages.

    Returns messages in the rtmidi shape: ``[status, data1, data2]``.
    """

    if not 0 <= channel <= 15:
        raise ValueError("channel must be between 0 and 15")

    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    text = base64.b64encode(body).decode("ascii")
    status = MIDI_CONTROL_CHANGE | channel

    messages: list[list[int]] = [[status, CC_START, 0]]
    messages.extend([status, CC_DATA, ord(ch)] for ch in text)
    messages.append([status, CC_END, 0])
    return messages


@dataclass
class FrameDecoder:
    """Incrementally decode MIDI CC messages into JSON payloads."""

    channel: int = DEFAULT_CHANNEL
    _buffer: list[str] = field(default_factory=list)
    _active: bool = False

    def feed(self, message: list[int] | tuple[int, ...]) -> dict[str, Any] | None:
        if len(message) < 3:
            return None

        status, cc, value = int(message[0]), int(message[1]), int(message[2])
        if status != (MIDI_CONTROL_CHANGE | self.channel):
            return None

        if cc == CC_START:
            self._active = True
            self._buffer.clear()
            return None

        if not self._active:
            return None

        if cc == CC_DATA:
            if not 0 <= value <= 127:
                raise ProtocolError(f"invalid 7-bit MIDI value: {value}")
            self._buffer.append(chr(value))
            return None

        if cc == CC_END:
            raw = "".join(self._buffer)
            self._active = False
            self._buffer.clear()
            try:
                decoded = base64.b64decode(raw.encode("ascii"), validate=True)
                payload = json.loads(decoded.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001 - protocol boundary
                raise ProtocolError(f"invalid MIDI JSON frame: {exc}") from exc
            if not isinstance(payload, dict):
                raise ProtocolError("decoded payload is not an object")
            return payload

        return None

