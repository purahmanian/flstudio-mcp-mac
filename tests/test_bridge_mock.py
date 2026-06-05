import pytest

from flstudio_mcp_mac.bridge import BridgeError, MockBridge


def test_mock_bridge_mutates_state():
    bridge = MockBridge()

    assert bridge.call("get_status")["tempo"] == 120.0
    assert bridge.call("set_tempo", {"bpm": 128})["tempo"] == 128.0
    assert bridge.call("transport", {"action": "play"})["playing"] is True

    track = bridge.call(
        "set_mixer_track",
        {"index": 1, "name": "Lead Bus", "volume": 0.42, "muted": True},
    )["track"]

    assert track["name"] == "Lead Bus"
    assert track["volume"] == 0.42
    assert track["muted"] is True


def test_mock_bridge_rejects_unknown_command():
    bridge = MockBridge()

    with pytest.raises(BridgeError, match="unknown command"):
        bridge.call("render_project")
