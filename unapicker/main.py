"""CLI for unapicker file picker FUSE service."""

import argparse
import logging
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from unapicker.picker_fs import mount_picker_fs


def get_default_pickers() -> List[str]:
    """Get list of default picker commands to try (non-interactive only)."""
    return [
        "zenity --file-selection",
        "kdialog --getopenfilename /",
    ]


def cmd_daemon(args):
    """Run the picker filesystem daemon."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    pickers = args.pickers or get_default_pickers()
    mount_picker_fs(
        args.mount_point,
        pickers,
        foreground=args.foreground,
        cache_timeout=args.cache,
    )


def cmd_install_service(args):
    """Install systemd user service."""
    mount_point = "/tmp/picker"

    # Prompt for picker commands
    print("\nEnter picker commands (one per line, empty line to finish):")
    print("Default options:")
    for i, picker in enumerate(get_default_pickers(), 1):
        print(f"  {i}. {picker}")
    print()

    pickers = []
    while True:
        picker = input("Picker command: ").strip()
        if not picker:
            if not pickers:
                pickers = get_default_pickers()
            break
        pickers.append(picker)

    # Determine unapicker command path
    unapicker_path = shutil.which("unapicker")
    if not unapicker_path:
        # Try to find it in the current environment
        import unapicker

        unapicker_path = os.path.join(os.path.dirname(unapicker.__file__), "..", "unapicker")

    # Create systemd service file
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)
    service_file = service_dir / "unapicker.service"

    # Build picker command arguments
    picker_args = " ".join(f"--picker {shlex.quote(p)}" for p in pickers)
    exec_start = f"{unapicker_path} daemon --mount-point {mount_point} {picker_args}".strip()

    service_content = f"""[Unit]
Description=File Picker FUSE Mount
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
ExecStop=/bin/sh -c 'fusermount -u /tmp/.picker-fuse 2>/dev/null || true'
Restart=on-failure
RestartSec=5
RestartSteps=10
RestartMaxDelaySec=1h

[Install]
WantedBy=default.target
"""

    service_file.write_text(service_content)
    print(f"\n✓ Service file created: {service_file}")

    # Enable and start the service
    print("\nEnabling and starting service...")
    subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        check=True,
    )
    subprocess.run(
        ["systemctl", "--user", "enable", "unapicker.service"],
        check=True,
    )
    subprocess.run(
        ["systemctl", "--user", "start", "unapicker.service"],
        check=True,
    )

    print("✓ Service enabled and started")
    print(f"\nYour TUI app can now read from: {mount_point}")
    print("\n⚠ If the file picker doesn't work, add this to ~/.xinitrc or ~/.wayland-session:")
    print("  dbus-update-activation-environment --systemd DISPLAY WAYLAND_DISPLAY XAUTHORITY")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="File picker FUSE service for TUI applications"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # daemon subcommand
    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Run the picker filesystem daemon",
    )
    daemon_parser.add_argument(
        "--mount-point",
        default="/tmp/picker",
        help="Where to mount the filesystem (default: /tmp/picker)",
    )
    daemon_parser.add_argument(
        "--picker",
        action="append",
        dest="pickers",
        help="Picker command to try (can specify multiple, will try in order)",
    )
    daemon_parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground (for debugging)",
    )
    daemon_parser.add_argument(
        "--cache",
        type=int,
        default=5,
        help="Cache picker result for N seconds (default: 5)",
    )
    daemon_parser.set_defaults(func=cmd_daemon)

    # install_service subcommand
    install_parser = subparsers.add_parser(
        "install_service",
        help="Install and enable systemd user service",
    )
    install_parser.set_defaults(func=cmd_install_service)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
