from pathlib import Path

from flstudio_mcp_mac.install import install_scripts


def test_install_scripts_to_user_data_dir(tmp_path: Path):
    installed = install_scripts(tmp_path)

    controller = Path(installed["controller_script"])
    piano_roll = Path(installed["piano_roll_script"])

    assert controller.exists()
    assert piano_roll.exists()
    assert controller.name == "device_FLStudioMCP.py"
    assert piano_roll.name == "FL Studio MCP Apply.pyscript"

