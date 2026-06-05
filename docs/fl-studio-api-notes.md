# FL Studio API Notes

This project uses two FL Studio Python surfaces:

- MIDI Controller Scripting for live control and state reads.
- Piano Roll Scripting for persistent note insertion into the currently open Piano Roll.

The MIDI controller bridge intentionally avoids arbitrary Python execution inside FL Studio.
Commands are whitelisted in `device_FLStudioMCP.py` and results are returned as JSON over a
small MIDI CC framing protocol.

Useful references:

- Image-Line MIDI scripting reference: https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm
- FL Studio API stubs: https://il-group.github.io/FL-Studio-API-Stubs/
- Image-Line Piano Roll scripting reference: https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/pianoroll_scripting_api.htm

