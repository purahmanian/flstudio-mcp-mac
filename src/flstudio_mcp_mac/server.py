"""MCP tool surface for FL Studio on macOS."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from mcp.types import ToolAnnotations

from .bridge import BridgeError, get_bridge
from .midi_file import default_output_dir, write_midi_from_dicts

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_stem(name: str) -> str:
    stem = SAFE_NAME_RE.sub("-", name.strip()).strip("-._")
    return stem or "clip"


def _bridge_call(command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return get_bridge().call(command, params or {})
    except BridgeError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "hint": (
                "Start FL Studio, then configure MIDI settings with `FLStudioMCP Request` "
                "as the enabled controller input and `FLStudioMCP Response` as its output. "
                "The MCP server starts a singleton local MIDI daemon automatically."
            ),
        }


def create_app() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised by CLI users
        raise SystemExit(
            "The `mcp` package is required. Install this project with "
            "`pip install -e .` or install dependencies from pyproject.toml."
        ) from exc

    mcp = FastMCP("FL Studio MCP Mac")

    @mcp.tool(
        annotations=ToolAnnotations(
            title='FL Studio health + status',
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    def fl_health() -> dict[str, Any]:
        """Check the FL Studio bridge and return live project status when connected."""

        result = _bridge_call("get_status")
        if result.get("ok") is False:
            return result
        return {"ok": True, "status": result}

    @mcp.tool(
        annotations=ToolAnnotations(
            title='FL Studio transport control',
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    def fl_transport(
        action: Literal[
            "play",
            "stop",
            "record_toggle",
            "rewind",
            "song_mode",
            "pattern_mode",
            "metronome_toggle",
        ],
    ) -> dict[str, Any]:
        """Control FL Studio transport."""

        return _bridge_call("transport", {"action": action})

    @mcp.tool(
        annotations=ToolAnnotations(
            title='Set project tempo',
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    def fl_set_tempo(bpm: float) -> dict[str, Any]:
        """Set the current FL Studio project tempo."""

        if bpm < 20 or bpm > 999:
            return {"ok": False, "error": "bpm must be between 20 and 999"}
        return _bridge_call("set_tempo", {"bpm": bpm})

    @mcp.tool(
        annotations=ToolAnnotations(
            title='Read mixer tracks',
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    def fl_mixer_tracks(limit: int = 32) -> dict[str, Any]:
        """Read mixer track names, volume, pan, mute, and solo state."""

        if limit < 1 or limit > 128:
            return {"ok": False, "error": "limit must be between 1 and 128"}
        return _bridge_call("mixer_tracks", {"limit": limit})

    @mcp.tool(
        annotations=ToolAnnotations(
            title='Set mixer track',
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    def fl_set_mixer_track(
        index: int,
        volume: float | None = None,
        pan: float | None = None,
        muted: bool | None = None,
        solo: bool | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Mutate a single mixer track by explicit index."""

        params: dict[str, Any] = {"index": index}
        if volume is not None:
            if volume < 0 or volume > 1:
                return {"ok": False, "error": "volume must be between 0 and 1"}
            params["volume"] = volume
        if pan is not None:
            if pan < -1 or pan > 1:
                return {"ok": False, "error": "pan must be between -1 and 1"}
            params["pan"] = pan
        if muted is not None:
            params["muted"] = muted
        if solo is not None:
            params["solo"] = solo
        if name is not None:
            params["name"] = name
        return _bridge_call("set_mixer_track", params)

    @mcp.tool(
        annotations=ToolAnnotations(
            title='Read channel rack',
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    def fl_channels(limit: int = 64) -> dict[str, Any]:
        """Read Channel Rack channel state."""

        if limit < 1 or limit > 256:
            return {"ok": False, "error": "limit must be between 1 and 256"}
        return _bridge_call("channels", {"limit": limit})

    @mcp.tool(
        annotations=ToolAnnotations(
            title='Set channel',
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    def fl_set_channel(
        index: int,
        selected: bool | None = None,
        volume: float | None = None,
        pan: float | None = None,
        muted: bool | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Mutate a Channel Rack channel by explicit index."""

        params: dict[str, Any] = {"index": index}
        if selected is not None:
            params["selected"] = selected
        if volume is not None:
            if volume < 0 or volume > 1:
                return {"ok": False, "error": "volume must be between 0 and 1"}
            params["volume"] = volume
        if pan is not None:
            if pan < -1 or pan > 1:
                return {"ok": False, "error": "pan must be between -1 and 1"}
            params["pan"] = pan
        if muted is not None:
            params["muted"] = muted
        if name is not None:
            params["name"] = name
        return _bridge_call("set_channel", params)

    @mcp.tool(
        annotations=ToolAnnotations(
            title='Create MIDI file',
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    def fl_create_midi_file(
        name: str,
        notes: list[dict[str, Any]],
        tempo_bpm: float = 120.0,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        """Create a Standard MIDI file that can be imported into FL Studio."""

        directory = Path(output_dir).expanduser() if output_dir else default_output_dir()
        path = directory / f"{_safe_stem(name)}.mid"
        try:
            write_midi_from_dicts(path, notes, tempo_bpm=tempo_bpm)
        except Exception as exc:  # noqa: BLE001 - tool boundary
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "path": str(path), "note_count": len(notes)}

    @mcp.tool(
        annotations=ToolAnnotations(
            title='Queue Piano Roll notes',
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    def fl_queue_piano_roll_notes(
        notes: list[dict[str, Any]],
        clear_existing: bool = False,
        queue_path: str | None = None,
    ) -> dict[str, Any]:
        """Queue notes for the included FL Studio Piano Roll script to apply."""

        target = (
            Path(queue_path).expanduser()
            if queue_path
            else Path.home() / "Music" / "FLStudioMCP" / "piano_roll_queue.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"clear_existing": clear_existing, "notes": notes}
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "ok": True,
            "path": str(target),
            "next_step": "Open the target channel's Piano Roll and run Scripts > FL Studio MCP Apply.",
        }

    return mcp


def main() -> None:
    create_app().run()


if __name__ == "__main__":
    main()
