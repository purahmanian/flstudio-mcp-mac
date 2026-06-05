# FL Studio MCP Mac

<!-- mcp-name: io.github.purahmanian/flstudio-mcp-mac -->

macOS-first MCP bridge for FL Studio. It exposes FL Studio transport, mixer, channel, MIDI export, and Piano Roll note-apply workflows to MCP clients such as Claude Desktop, Claude Code, Cursor, and other MCP-capable tools.

This is an alpha MVP. It is intentionally scoped around FL Studio's documented Python MIDI scripting and Piano Roll scripting APIs. It does not promise full headless FL Studio automation.

## Why This Exists

Most FL Studio MCP work today is Windows-oriented. macOS has a cleaner CoreMIDI path for virtual ports, and FL Studio supports Python-based MIDI scripts on macOS. This project turns that into a small local MCP server plus companion FL Studio scripts.

## What Works

- Live bridge over macOS virtual MIDI ports.
- FL Studio status and health checks.
- Transport: play, stop, record toggle, rewind, song/pattern mode, metronome toggle.
- Tempo changes.
- Mixer track reads and explicit track mutations.
- Channel Rack reads and explicit channel mutations.
- Standard MIDI file generation for import into FL Studio.
- Piano Roll queue file plus an included `.pyscript` to insert persistent notes.

## Known Limits

- FL Studio's MIDI scripting API is not a complete DAW API.
- Loading plugins, loading arbitrary audio files, and rendering/exporting are not implemented here.
- Persistent note writing goes through the included Piano Roll script. The MCP server queues notes; you run `Scripts > FL Studio MCP Apply` in the target Piano Roll.
- Live bridge setup requires FL Studio's MIDI settings to map the request/response ports. The MCP server starts a singleton local MIDI daemon so Claude Desktop, Claude Code, and terminal tests share the same CoreMIDI endpoints.

## Install

From this repo:

```bash
python3 -m pip install .
flstudio-mcp-mac-install
```

The installer copies:

- `device_FLStudioMCP.py` to `~/Documents/Image-Line/FL Studio/Settings/Hardware/FLStudioMCP/`
- `FL Studio MCP Apply.pyscript` to `~/Documents/Image-Line/FL Studio/Settings/Piano roll scripts/`

## Configure FL Studio on macOS

1. Start the MCP server once so it starts the local MIDI daemon and creates the virtual CoreMIDI ports:

   ```bash
   flstudio-mcp-mac
   ```

   You can stop this foreground MCP process after the ports appear. The background daemon keeps the `FLStudioMCP Request` and `FLStudioMCP Response` ports available for all MCP clients.

2. Open FL Studio and go to `Options > MIDI Settings`.
3. In the input list, choose `FLStudioMCP Request`.
4. Set `Controller type` to `FL Studio MCP Mac`.
5. Set the controller output to `FLStudioMCP Response`.
6. Restart the MCP client if needed. If duplicate `FLStudioMCP` ports appear, quit old MCP server processes and start the v0.1.1+ daemon again.

## MCP Client Config

For detailed setup across Claude Desktop, Claude Code, Cursor, Windsurf, PyPI, and the MCP Registry, see [docs/publishing.md](docs/publishing.md).

Example Claude Desktop config:

```json
{
  "mcpServers": {
    "flstudio-mcp-mac": {
      "command": "flstudio-mcp-mac"
    }
  }
}
```

For source installs where the command is not on PATH:

```json
{
  "mcpServers": {
    "flstudio-mcp-mac": {
      "command": "python3",
      "args": ["-m", "flstudio_mcp_mac"]
    }
  }
}
```

## MIDI Note Workflow

Use `fl_create_midi_file` when you want a normal `.mid` file to import.

Use `fl_queue_piano_roll_notes` when you want to apply notes into the currently open Piano Roll:

1. Ask the MCP client to queue notes.
2. In FL Studio, open the target channel's Piano Roll.
3. Run `Scripts > FL Studio MCP Apply`.

Note shape:

```json
[
  { "pitch": 60, "start": 0, "duration": 1, "velocity": 100 },
  { "pitch": 64, "start": 1, "duration": 1, "velocity": 96 },
  { "pitch": 67, "start": 2, "duration": 2, "velocity": 96 }
]
```

Times are in beats. MIDI pitch uses the standard 0-127 scale.

## Development

```bash
python3 -m pip install ".[dev]"
PYTHONPATH=src pytest
```

Set `FLSTUDIO_MCP_BRIDGE=mock` to run the MCP server with deterministic in-memory FL Studio responses for protocol tests:

```bash
FLSTUDIO_MCP_BRIDGE=mock python3 -m flstudio_mcp_mac
```

Normal live mode uses a background daemon. For low-level debugging, set `FLSTUDIO_MCP_BRIDGE=direct` to make one MCP process own the virtual MIDI ports directly.

For live FL Studio validation steps, see [docs/testing.md](docs/testing.md).

## Protocol

The bridge sends base64 JSON over MIDI control-change frames on channel 16:

- CC 120: frame start
- CC 121: one base64 character
- CC 122: frame end

The FL script only accepts whitelisted command names and returns one JSON response for each request.
