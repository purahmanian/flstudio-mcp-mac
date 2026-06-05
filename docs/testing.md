# Testing FL Studio MCP Mac

This project has two test layers:

- Local Python tests validate packaging, protocol framing, MIDI-file output, installer paths, and MCP helper behavior.
- A live FL Studio smoke test validates the CoreMIDI bridge and companion FL scripts.

## Local Tests

From the repo root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install ".[dev]"
PYTHONPATH=src .venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src tests
.venv/bin/python -m py_compile fl_scripts/midi_controller/FLStudioMCP/device_FLStudioMCP.py
.venv/bin/python -m py_compile "fl_scripts/piano_roll/FL Studio MCP Apply.pyscript"
```

The test suite includes a real stdio MCP client/server round trip. It starts the server with:

```bash
FLSTUDIO_MCP_BRIDGE=mock
```

That mock mode lists the real MCP tools and exercises all tool handlers without requiring FL Studio.

Installer smoke test:

```bash
.venv/bin/flstudio-mcp-mac-install --user-data-dir /tmp/flstudio-mcp-mac-test-install
find /tmp/flstudio-mcp-mac-test-install -type f
```

Source import smoke test:

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from flstudio_mcp_mac.server import create_app

app = create_app()
print(type(app).__name__)
PY
```

Package install smoke test:

```bash
.venv/bin/python -m pip install build
rm -rf dist build
.venv/bin/python -m build
python3 -m venv /tmp/flstudio-mcp-mac-wheel-venv
/tmp/flstudio-mcp-mac-wheel-venv/bin/python -m pip install dist/flstudio_mcp_mac-0.1.2-py3-none-any.whl
/tmp/flstudio-mcp-mac-wheel-venv/bin/python - <<'PY'
from flstudio_mcp_mac.server import create_app

app = create_app()
print(type(app).__name__)
PY
/tmp/flstudio-mcp-mac-wheel-venv/bin/flstudio-mcp-mac-install --user-data-dir /tmp/flstudio-mcp-mac-wheel-install
find /tmp/flstudio-mcp-mac-wheel-install -type f
```

## Live FL Studio Smoke Test

Install the package and FL Studio companion scripts:

```bash
python3 -m pip install .
flstudio-mcp-mac-install
```

Start the MCP server in a terminal once. This starts the singleton MIDI daemon and creates the CoreMIDI ports:

```bash
flstudio-mcp-mac
```

You may stop the foreground MCP server after the ports appear. The daemon keeps running in the background and owns the virtual MIDI ports for all MCP clients and terminal tests.

Open FL Studio on macOS, then configure MIDI:

1. Open `Options > MIDI Settings`.
2. In the input list, choose `FLStudioMCP Request`.
3. Enable the input if FL Studio does not enable it automatically.
4. Set `Controller type` to `FL Studio MCP Mac`.
5. Set the controller output to `FLStudioMCP Response`.
6. Restart the MCP client after changing config.

Then call these tools from Claude Desktop, Claude Code, Cursor, or another MCP client:

```text
fl_health
fl_set_tempo tempo=128
fl_transport action=play
fl_transport action=stop
fl_mixer_tracks
fl_channels
```

Expected results:

- `fl_health` returns a JSON response with FL Studio bridge status.
- `fl_set_tempo` changes the FL Studio project tempo.
- `fl_transport` starts and stops playback.
- Mixer and channel tools return visible tracks/channels from the current project.

The same live path can be tested from a terminal. Do not set `FLSTUDIO_MCP_BRIDGE=direct`; the default daemon mode is what prevents duplicate CoreMIDI endpoints:

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from flstudio_mcp_mac.server import _bridge_call

print(_bridge_call("get_status"))
print(_bridge_call("set_tempo", {"bpm": 128}))
print(_bridge_call("transport", {"action": "play"}))
print(_bridge_call("transport", {"action": "stop"}))
PY
```

## MIDI File Test

Call `fl_create_midi_file` with a short chord progression. The tool writes a `.mid` file, which you can import into FL Studio.

Example note payload:

```json
[
  { "pitch": 60, "start": 0, "duration": 1, "velocity": 100 },
  { "pitch": 64, "start": 0, "duration": 1, "velocity": 96 },
  { "pitch": 67, "start": 0, "duration": 1, "velocity": 96 }
]
```

## Piano Roll Apply Test

Call `fl_queue_piano_roll_notes` with a short phrase. It writes:

```text
~/Music/FLStudioMCP/piano_roll_queue.json
```

In FL Studio:

1. Open the target channel's Piano Roll.
2. Run `Scripts > FL Studio MCP Apply`.
3. Confirm the queued notes appear in the Piano Roll.

## Troubleshooting

- If `fl_health` times out, FL Studio is not connected to both virtual ports.
- If `FL Studio MCP Mac` is not listed as a controller type, rerun `flstudio-mcp-mac-install` and restart FL Studio.
- If commands reach FL Studio but never return, the controller output is probably not set to `FLStudioMCP Response`.
- If Piano Roll notes do not appear, confirm the queue file exists at `~/Music/FLStudioMCP/piano_roll_queue.json` and run the script from an open Piano Roll window.
- If the virtual ports do not show up, start `flstudio-mcp-mac` before opening FL Studio's MIDI settings.
- If duplicate `FLStudioMCP Request` or `FLStudioMCP Response` ports appear, quit old MCP server processes and restart the v0.1.1+ daemon. The old direct bridge mode creates per-process virtual ports; daemon mode creates one shared port pair.
- The daemon socket defaults to `~/Library/Application Support/flstudio-mcp-mac/bridge.sock`, and logs default to `~/Library/Application Support/flstudio-mcp-mac/daemon.log`.
