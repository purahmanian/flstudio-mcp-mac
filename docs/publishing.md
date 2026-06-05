# Publishing FL Studio MCP Mac

This server is a local stdio MCP server that talks to FL Studio through macOS CoreMIDI. The right distribution path is local installation first, then package registries. A hosted remote MCP server is not useful by itself because FL Studio and the MIDI ports live on the user's Mac.

## Current State

- GitHub repo: `https://github.com/purahmanian/flstudio-mcp-mac`
- Python package name: `flstudio-mcp-mac`
- MCP registry name: `io.github.purahmanian/flstudio-mcp-mac`
- Transport: `stdio`
- macOS only for the live bridge

## Install From GitHub

For now, users can install from the public repo:

```bash
python3 -m pip install "flstudio-mcp-mac @ git+https://github.com/purahmanian/flstudio-mcp-mac.git"
flstudio-mcp-mac-install
```

For development:

```bash
git clone https://github.com/purahmanian/flstudio-mcp-mac.git
cd flstudio-mcp-mac
python3 -m pip install ".[dev]"
flstudio-mcp-mac-install
```

## Claude Code

Claude Code can add a local stdio server with `claude mcp add`:

```bash
claude mcp add flstudio-mcp-mac -- flstudio-mcp-mac
```

For a source checkout where the console script is not on `PATH`, use the virtualenv Python:

```bash
claude mcp add flstudio-mcp-mac -- /Users/puyarahmanian/Documents/New\ project/.venv/bin/python -m flstudio_mcp_mac
```

Useful checks:

```bash
claude mcp list
claude mcp get flstudio-mcp-mac
```

Inside Claude Code, run `/mcp` to inspect connection status.

## Claude Desktop

Claude Desktop supports local MCP servers through local configuration and now also supports desktop extensions.

Manual config fallback:

```json
{
  "mcpServers": {
    "flstudio-mcp-mac": {
      "type": "stdio",
      "command": "flstudio-mcp-mac",
      "args": []
    }
  }
}
```

If the command is not on `PATH`:

```json
{
  "mcpServers": {
    "flstudio-mcp-mac": {
      "type": "stdio",
      "command": "/Users/puyarahmanian/Documents/New project/.venv/bin/python",
      "args": ["-m", "flstudio_mcp_mac"]
    }
  }
}
```

Restart Claude Desktop after editing the config. Check the server from Claude Desktop's connector/developer settings if tools do not appear.

## Claude Desktop Extension

For broader Claude Desktop distribution, package this as a desktop extension. The repo includes `manifest.json`, `.mcpbignore`, and `mcpb_entry.py` for MCPB packaging:

```bash
npm install -g @anthropic-ai/mcpb
mcpb validate manifest.json
mcpb pack . dist/flstudio-mcp-mac-0.1.1.mcpb
```

Then double-click the generated `.mcpb`, drag it into Claude Desktop, or install it from `Settings > Extensions > Advanced settings > Install Extension`.

This uses the MCPB `uv` runtime support so the extension can install Python dependencies from `pyproject.toml`. In v0.1.1 and later, the extension starts the singleton MIDI daemon automatically so Claude Desktop shares the same `FLStudioMCP Request` and `FLStudioMCP Response` ports with terminal tests and other local MCP clients.

## Claude.ai Remote Connectors

Claude.ai custom connectors are remote MCP servers reached from Anthropic's cloud infrastructure. This FL Studio bridge is local-only, so a remote connector would not be able to see the user's FL Studio MIDI ports unless we also build a separate local agent and remote relay.

For this project, prefer:

- Claude Desktop local extension for nontechnical users.
- Claude Code local stdio config for developers.
- Cursor/Windsurf local MCP config for editor users.

## Cursor, Windsurf, And Other MCP Clients

Use the same stdio command:

```json
{
  "mcpServers": {
    "flstudio-mcp-mac": {
      "command": "flstudio-mcp-mac",
      "args": []
    }
  }
}
```

If installed from source, point `command` at the virtualenv Python and pass `["-m", "flstudio_mcp_mac"]` as args.

## PyPI

PyPI should be the next public distribution milestone:

```bash
python3 -m pip install build twine
python3 -m build
python3 -m twine upload dist/*
```

After PyPI is live, users can install with:

```bash
python3 -m pip install flstudio-mcp-mac
flstudio-mcp-mac-install
```

The README already includes the hidden MCP registry verification line:

```html
<!-- mcp-name: io.github.purahmanian/flstudio-mcp-mac -->
```

## MCP Registry

The repo includes a `server.json` prepared for the MCP Registry. Publish only after the PyPI package exists:

```bash
mcp-publisher login github
mcp-publisher publish
```

The registry hosts metadata, not the package artifact. The actual code artifact should live on PyPI, and `server.json` points clients to that package with stdio transport.

## Catalogs

After PyPI and MCP Registry publication, submit the GitHub repo to community directories such as Smithery, Glama, PulseMCP, and mcp.so. These are discovery surfaces; they do not replace PyPI or the Claude Desktop extension package.
