from pathlib import Path

import pytest

from flstudio_mcp_mac.midi_file import MidiNote, write_midi_file


def test_write_midi_file(tmp_path: Path):
    path = tmp_path / "clip.mid"

    result = write_midi_file(
        path,
        [
            MidiNote(pitch=60, start=0, duration=1, velocity=100),
            MidiNote(pitch=64, start=1, duration=1, velocity=90),
        ],
        tempo_bpm=120,
    )

    data = result.read_bytes()
    assert result == path
    assert data.startswith(b"MThd")
    assert b"MTrk" in data
    assert data.endswith(b"\x00\xff\x2f\x00")


def test_write_midi_rejects_invalid_note(tmp_path: Path):
    with pytest.raises(ValueError, match="pitch"):
        write_midi_file(tmp_path / "bad.mid", [MidiNote(pitch=200, start=0, duration=1)])

