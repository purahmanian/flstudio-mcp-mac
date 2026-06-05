from flstudio_mcp_mac.protocol import FrameDecoder, encode_payload


def test_protocol_round_trip():
    payload = {
        "id": "abc",
        "command": "set_tempo",
        "params": {"bpm": 128.5},
    }

    decoder = FrameDecoder()
    decoded = None
    for message in encode_payload(payload):
        decoded = decoder.feed(message)

    assert decoded == payload


def test_protocol_ignores_other_channel():
    decoder = FrameDecoder(channel=15)
    messages = encode_payload({"id": "x"}, channel=0)

    assert [decoder.feed(message) for message in messages] == [None] * len(messages)

