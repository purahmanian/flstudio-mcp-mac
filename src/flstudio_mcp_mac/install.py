"""Install FL Studio companion scripts."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def default_user_data_dir() -> Path:
    return Path.home() / "Documents" / "Image-Line" / "FL Studio" / "Settings"


def script_source_dir() -> Path:
    package_dir = Path(__file__).resolve().parent
    packaged = package_dir / "fl_scripts"
    if packaged.exists():
        return packaged

    source_tree = package_dir.parents[1] / "fl_scripts"
    if source_tree.exists():
        return source_tree

    raise FileNotFoundError("could not locate bundled FL Studio scripts")


def install_scripts(user_data_dir: Path | None = None) -> dict[str, str]:
    root = user_data_dir or default_user_data_dir()
    source = script_source_dir()

    hardware_target = root / "Hardware" / "FLStudioMCP"
    piano_roll_target = root / "Piano roll scripts"
    hardware_target.mkdir(parents=True, exist_ok=True)
    piano_roll_target.mkdir(parents=True, exist_ok=True)

    controller_source = source / "midi_controller" / "FLStudioMCP" / "device_FLStudioMCP.py"
    piano_roll_source = source / "piano_roll" / "FL Studio MCP Apply.pyscript"

    controller_target = hardware_target / "device_FLStudioMCP.py"
    piano_roll_script_target = piano_roll_target / "FL Studio MCP Apply.pyscript"

    shutil.copy2(controller_source, controller_target)
    shutil.copy2(piano_roll_source, piano_roll_script_target)

    return {
        "controller_script": str(controller_target),
        "piano_roll_script": str(piano_roll_script_target),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Install FL Studio MCP companion scripts.")
    parser.add_argument(
        "--user-data-dir",
        type=Path,
        default=None,
        help="FL Studio Settings folder. Defaults to ~/Documents/Image-Line/FL Studio/Settings.",
    )
    args = parser.parse_args()
    installed = install_scripts(args.user_data_dir)
    for label, path in installed.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
