from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def test_mcp_stdio_tool_round_trip(tmp_path: Path):
    anyio.run(_run_mcp_stdio_round_trip, tmp_path)


async def _run_mcp_stdio_round_trip(tmp_path: Path):
    env = {
        **os.environ,
        "PYTHONPATH": str(SRC_ROOT),
        "FLSTUDIO_MCP_BRIDGE": "mock",
    }
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "flstudio_mcp_mac"],
        env=env,
        cwd=str(PROJECT_ROOT),
    )

    async with stdio_client(server) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {tool.name for tool in tools.tools}

            assert tool_names == {
                "fl_health",
                "fl_transport",
                "fl_set_tempo",
                "fl_mixer_tracks",
                "fl_set_mixer_track",
                "fl_channels",
                "fl_set_channel",
                "fl_create_midi_file",
                "fl_queue_piano_roll_notes",
            }

            health = await session.call_tool("fl_health")
            assert health.structuredContent["ok"] is True
            assert health.structuredContent["status"]["mock"] is True

            tempo = await session.call_tool("fl_set_tempo", {"bpm": 128})
            assert tempo.structuredContent["tempo"] == 128

            transport = await session.call_tool("fl_transport", {"action": "play"})
            assert transport.structuredContent["playing"] is True

            tracks = await session.call_tool("fl_mixer_tracks", {"limit": 1})
            assert tracks.structuredContent["count"] == 2
            assert len(tracks.structuredContent["tracks"]) == 1

            mixer_update = await session.call_tool(
                "fl_set_mixer_track",
                {"index": 1, "name": "Lead Bus", "volume": 0.5, "muted": True},
            )
            assert mixer_update.structuredContent["track"]["name"] == "Lead Bus"
            assert mixer_update.structuredContent["track"]["muted"] is True

            channels = await session.call_tool("fl_channels", {"limit": 2})
            assert channels.structuredContent["count"] == 2

            channel_update = await session.call_tool(
                "fl_set_channel",
                {"index": 1, "selected": True, "name": "Keys Layer"},
            )
            assert channel_update.structuredContent["channel"]["name"] == "Keys Layer"
            assert channel_update.structuredContent["channel"]["selected"] is True

            notes = [
                {"pitch": 60, "start": 0, "duration": 1, "velocity": 100},
                {"pitch": 64, "start": 1, "duration": 1, "velocity": 96},
            ]
            midi = await session.call_tool(
                "fl_create_midi_file",
                {"name": "MCP Test Clip", "notes": notes, "output_dir": str(tmp_path)},
            )
            midi_path = Path(midi.structuredContent["path"])
            assert midi_path.exists()
            assert midi_path.name == "MCP-Test-Clip.mid"
            assert midi_path.read_bytes().startswith(b"MThd")

            queue_path = tmp_path / "piano_roll_queue.json"
            queued = await session.call_tool(
                "fl_queue_piano_roll_notes",
                {"notes": notes, "clear_existing": True, "queue_path": str(queue_path)},
            )
            assert queued.structuredContent["path"] == str(queue_path)
            payload = json.loads(queue_path.read_text(encoding="utf-8"))
            assert payload == {"clear_existing": True, "notes": notes}
