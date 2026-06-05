"""Tiny Standard MIDI File writer for FL-ready clips."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_TICKS_PER_BEAT = 480


@dataclass(frozen=True)
class MidiNote:
    pitch: int
    start: float
    duration: float
    velocity: int = 96
    channel: int = 0

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "MidiNote":
        return cls(
            pitch=int(value["pitch"]),
            start=float(value.get("start", 0.0)),
            duration=float(value.get("duration", 1.0)),
            velocity=int(value.get("velocity", 96)),
            channel=int(value.get("channel", 0)),
        )

    def validate(self) -> None:
        if not 0 <= self.pitch <= 127:
            raise ValueError("pitch must be 0..127")
        if self.start < 0:
            raise ValueError("start must be >= 0")
        if self.duration <= 0:
            raise ValueError("duration must be > 0")
        if not 1 <= self.velocity <= 127:
            raise ValueError("velocity must be 1..127")
        if not 0 <= self.channel <= 15:
            raise ValueError("channel must be 0..15")


def default_output_dir() -> Path:
    return Path.home() / "Music" / "FLStudioMCP" / "midi"


def write_midi_file(
    path: Path,
    notes: list[MidiNote],
    *,
    tempo_bpm: float = 120.0,
    ticks_per_beat: int = DEFAULT_TICKS_PER_BEAT,
) -> Path:
    if not notes:
        raise ValueError("at least one note is required")
    if tempo_bpm <= 0:
        raise ValueError("tempo_bpm must be > 0")
    if ticks_per_beat <= 0:
        raise ValueError("ticks_per_beat must be > 0")

    for note in notes:
        note.validate()

    path.parent.mkdir(parents=True, exist_ok=True)
    events: list[tuple[int, int, int, int, int]] = []
    for note in notes:
        start_tick = int(round(note.start * ticks_per_beat))
        end_tick = int(round((note.start + note.duration) * ticks_per_beat))
        events.append((start_tick, 0, 0x90 | note.channel, note.pitch, note.velocity))
        events.append((end_tick, 1, 0x80 | note.channel, note.pitch, 0))

    events.sort(key=lambda item: (item[0], item[1]))

    track = bytearray()
    tempo_us = int(round(60_000_000 / tempo_bpm))
    track.extend(_vlq(0))
    track.extend(b"\xff\x51\x03")
    track.extend(tempo_us.to_bytes(3, "big"))

    previous_tick = 0
    for tick, _order, status, pitch, velocity in events:
        track.extend(_vlq(tick - previous_tick))
        track.extend(bytes([status, pitch, velocity]))
        previous_tick = tick

    track.extend(_vlq(0))
    track.extend(b"\xff\x2f\x00")

    data = bytearray()
    data.extend(b"MThd")
    data.extend((6).to_bytes(4, "big"))
    data.extend((0).to_bytes(2, "big"))  # format 0
    data.extend((1).to_bytes(2, "big"))
    data.extend(ticks_per_beat.to_bytes(2, "big"))
    data.extend(b"MTrk")
    data.extend(len(track).to_bytes(4, "big"))
    data.extend(track)
    path.write_bytes(data)
    return path


def write_midi_from_dicts(
    path: Path,
    note_dicts: list[dict[str, Any]],
    *,
    tempo_bpm: float = 120.0,
    ticks_per_beat: int = DEFAULT_TICKS_PER_BEAT,
) -> Path:
    notes = [MidiNote.from_mapping(item) for item in note_dicts]
    return write_midi_file(path, notes, tempo_bpm=tempo_bpm, ticks_per_beat=ticks_per_beat)


def _vlq(value: int) -> bytes:
    if value < 0:
        raise ValueError("VLQ value must be >= 0")
    buffer = value & 0x7F
    value >>= 7
    while value:
        buffer <<= 8
        buffer |= ((value & 0x7F) | 0x80)
        value >>= 7

    out = bytearray()
    while True:
        out.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(out)
