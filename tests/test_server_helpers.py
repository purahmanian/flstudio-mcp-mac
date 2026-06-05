from flstudio_mcp_mac.server import _safe_stem


def test_safe_stem():
    assert _safe_stem("Deep House Loop 01") == "Deep-House-Loop-01"
    assert _safe_stem("...") == "clip"

