# name=FL Studio MCP Mac

import base64
import json

import channels
import device
import general
import midi
import mixer
import patterns
import transport
import ui

MIDI_CONTROL_CHANGE = 0xB0
CHANNEL = 15
CC_START = 120
CC_DATA = 121
CC_END = 122

_buffer = []
_active = False


def OnInit():
    ui.setHintMsg("FL Studio MCP Mac bridge ready")


def OnMidiMsg(event):
    global _active
    if not _is_bridge_cc(event):
        return

    event.handled = True
    cc = int(event.data1)
    value = int(event.data2)

    if cc == CC_START:
        _buffer[:] = []
        _active = True
        return

    if not _active:
        return

    if cc == CC_DATA:
        _buffer.append(chr(value))
        return

    if cc == CC_END:
        text = "".join(_buffer)
        _buffer[:] = []
        _active = False
        _dispatch_frame(text)


def _is_bridge_cc(event):
    midi_id = getattr(event, "midiId", None)
    midi_chan = getattr(event, "midiChan", None)
    if midi_id is not None:
        return int(midi_id) == midi.MIDI_CONTROLCHANGE and int(midi_chan) == CHANNEL

    status = int(getattr(event, "status", 0))
    return status == (MIDI_CONTROL_CHANGE | CHANNEL)


def _dispatch_frame(text):
    try:
        payload = json.loads(base64.b64decode(text.encode("ascii")).decode("utf-8"))
        request_id = payload.get("id")
        command = payload.get("command")
        params = payload.get("params") or {}
        result = _handle_command(command, params)
        _send_response(request_id, True, result, None)
    except Exception as exc:
        request_id = None
        try:
            request_id = payload.get("id")
        except Exception:
            pass
        _send_response(request_id, False, {}, str(exc))


def _send_response(request_id, ok, result, error):
    payload = {"id": request_id, "ok": ok, "result": result or {}}
    if error:
        payload["error"] = error
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    text = base64.b64encode(body).decode("ascii")

    device.midiOutMsg(_pack_cc(CC_START, 0))
    for char in text:
        device.midiOutMsg(_pack_cc(CC_DATA, ord(char)))
    device.midiOutMsg(_pack_cc(CC_END, 0))


def _pack_cc(cc, value):
    status = MIDI_CONTROL_CHANGE | CHANNEL
    return status | (int(cc) << 8) | (int(value) << 16)


def _handle_command(command, params):
    if command == "get_status":
        return _get_status()
    if command == "transport":
        return _transport(params)
    if command == "set_tempo":
        bpm = float(params["bpm"])
        mixer.setCurrentTempo(bpm)
        return _get_status()
    if command == "mixer_tracks":
        return _mixer_tracks(int(params.get("limit", 32)))
    if command == "set_mixer_track":
        return _set_mixer_track(params)
    if command == "channels":
        return _channels(int(params.get("limit", 64)))
    if command == "set_channel":
        return _set_channel(params)

    raise ValueError("unknown command: " + str(command))


def _get_status():
    return {
        "version": _safe_call(general.getVersion),
        "tempo": _safe_call(mixer.getCurrentTempo),
        "playing": bool(_safe_call(transport.isPlaying, False)),
        "recording": bool(_safe_call(transport.isRecording, False)),
        "loop_mode": int(_safe_call(transport.getLoopMode, 0)),
        "song_pos": _safe_call(transport.getSongPos),
        "song_length": _safe_call(transport.getSongLength),
        "selected_channel": _safe_call(channels.selectedChannel),
        "active_pattern": _safe_call(patterns.patternNumber),
        "mixer_track_count": _safe_call(mixer.trackCount),
    }


def _transport(params):
    action = params.get("action")
    if action == "play":
        transport.start()
    elif action == "stop":
        transport.stop()
    elif action == "record_toggle":
        transport.record()
    elif action == "rewind":
        transport.rewind()
    elif action == "song_mode":
        if int(transport.getLoopMode()) != 1:
            transport.setLoopMode()
    elif action == "pattern_mode":
        if int(transport.getLoopMode()) != 0:
            transport.setLoopMode()
    elif action == "metronome_toggle":
        transport.globalTransport(midi.FPT_Metronome, 1)
    else:
        raise ValueError("unsupported transport action: " + str(action))

    return _get_status()


def _mixer_tracks(limit):
    count = int(mixer.trackCount())
    selected = _safe_call(mixer.getTrackInfo, None, midi.TN_Sel)
    tracks = []
    for index in range(min(count, limit)):
        tracks.append(
            {
                "index": index,
                "name": _safe_call(mixer.getTrackName, "", index),
                "volume": _safe_call(mixer.getTrackVolume, None, index),
                "volume_db": _safe_call(mixer.getTrackVolume, None, index, 1),
                "pan": _safe_call(mixer.getTrackPan, None, index),
                "muted": bool(_safe_call(mixer.isTrackMuted, False, index)),
                "solo": bool(_safe_call(mixer.isTrackSolo, False, index)),
                "selected": index == selected,
            }
        )
    return {"tracks": tracks, "count": count}


def _set_mixer_track(params):
    index = int(params["index"])
    if "name" in params:
        mixer.setTrackName(index, str(params["name"]))
    if "volume" in params:
        mixer.setTrackVolume(index, float(params["volume"]))
    if "pan" in params:
        mixer.setTrackPan(index, float(params["pan"]))
    if "muted" in params:
        mixer.muteTrack(index, 1 if params["muted"] else 0)
    if "solo" in params:
        _set_mixer_solo(index, bool(params["solo"]))
    return {"track": _mixer_track(index)}


def _mixer_track(index):
    return {
        "index": index,
        "name": _safe_call(mixer.getTrackName, "", index),
        "volume": _safe_call(mixer.getTrackVolume, None, index),
        "pan": _safe_call(mixer.getTrackPan, None, index),
        "muted": bool(_safe_call(mixer.isTrackMuted, False, index)),
        "solo": bool(_safe_call(mixer.isTrackSolo, False, index)),
    }


def _set_mixer_solo(index, wanted):
    current = bool(_safe_call(mixer.isTrackSolo, False, index))
    if current != wanted:
        mixer.soloTrack(index)


def _channels(limit):
    count = int(channels.channelCount(True))
    selected = _safe_call(channels.selectedChannel, None, True, 0, True)
    items = []
    for index in range(min(count, limit)):
        items.append(_channel(index, selected))
    return {"channels": items, "count": count}


def _set_channel(params):
    index = int(params["index"])
    if "selected" in params and params["selected"]:
        channels.selectOneChannel(index, True)
    if "name" in params:
        channels.setChannelName(index, str(params["name"]), True)
    if "volume" in params:
        channels.setChannelVolume(index, float(params["volume"]), midi.PIM_None, True)
    if "pan" in params:
        channels.setChannelPan(index, float(params["pan"]), midi.PIM_None, True)
    if "muted" in params:
        channels.muteChannel(index, 1 if params["muted"] else 0, True)
    selected = _safe_call(channels.selectedChannel, None, True, 0, True)
    return {"channel": _channel(index, selected)}


def _channel(index, selected):
    return {
        "index": index,
        "name": _safe_call(channels.getChannelName, "", index, True),
        "volume": _safe_call(channels.getChannelVolume, None, index, False, True),
        "pan": _safe_call(channels.getChannelPan, None, index, True),
        "muted": bool(_safe_call(channels.isChannelMuted, False, index, True)),
        "solo": bool(_safe_call(channels.isChannelSolo, False, index, True)),
        "selected": index == selected,
        "target_mixer_track": _safe_call(channels.getTargetFxTrack, None, index, True),
    }


def _safe_call(fn, default=None, *args):
    try:
        return fn(*args)
    except Exception:
        return default

