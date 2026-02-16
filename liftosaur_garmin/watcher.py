"""Install and manage Liftosaur file watchers."""

from __future__ import annotations

import logging
import platform
import shutil
import stat
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _log_and_validate_python_path(python_path: str) -> None:
    logger.info(f"Watcher will use Python: {python_path}")
    print(f"   Python: {python_path}")

    expected_venv = (Path.cwd() / ".venv").resolve()
    resolved_python = Path(python_path).resolve()
    expected_prefix = f"{expected_venv}{Path.sep}"
    in_expected_venv = False
    try:
        in_expected_venv = resolved_python.is_relative_to(expected_venv)
    except Exception:
        in_expected_venv = str(resolved_python).startswith(expected_prefix)

    if not in_expected_venv:
        warning = (
            "⚠️  Watcher Python does not appear to be from this project's .venv: "
            f"{expected_venv}"
        )
        logger.warning(warning)
        print(f"   {warning}")


def get_default_watch_dir() -> Path | None:
    """Return the default Liftosaur iCloud directory when available."""
    if platform.system() != "Darwin":
        return None

    candidate = (
        Path("~/.".rstrip("."))  # no-op to keep ASCII and avoid linting artifacts
    )
    watch_dir = Path(
        "~/Library/Mobile Documents/com~apple~CloudDocs/Liftosaur"
    ).expanduser()
    if watch_dir.exists():
        return watch_dir
    return None


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def render_template(template_name: str, variables: dict) -> str:
    """Render a template file by replacing {{key}} placeholders."""
    template_path = _templates_dir() / template_name
    content = template_path.read_text(encoding="utf-8")
    for key, value in variables.items():
        placeholder = "{{" + str(key) + "}}"
        content = content.replace(placeholder, str(value))
    return content


def install_watcher(
    profile_name: str,
    profile_dir: Path,
    watch_dir: Path,
    python_path: str,
    poll_interval: int | None = None,
) -> bool:
    """Install a watcher appropriate for the current OS."""
    _log_and_validate_python_path(python_path)
    system = platform.system()
    if system == "Darwin":
        return _install_launchd(
            profile_name,
            profile_dir,
            watch_dir,
            python_path,
            poll_interval,
        )
    if system == "Linux":
        return _install_systemd(profile_name, profile_dir, watch_dir, python_path)

    print(
        "⚠️  Automatic file watching is not yet supported on Windows. "
        "You can run the tool manually or set up Task Scheduler."
    )
    return False


def _install_launchd(
    profile_name: str,
    profile_dir: Path,
    watch_dir: Path,
    python_path: str,
    poll_interval: int | None = None,
) -> bool:
    profile_dir.mkdir(parents=True, exist_ok=True)
    script_path = profile_dir / "watch_and_process.sh"
    script_content = render_template(
        "watch_and_process.sh.template",
        {
            "watch_dir": watch_dir,
            "python_path": python_path,
            "profile_name": profile_name,
            "log_file": profile_dir / "watcher.log",
            "processed_file": profile_dir / "processed_files.txt",
        },
    )
    script_path.write_text(script_content, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    resolved_interval = 300
    if poll_interval is not None:
        try:
            resolved_interval = int(poll_interval)
        except (TypeError, ValueError):
            resolved_interval = 300
    if resolved_interval <= 0:
        resolved_interval = 300

    plist_content = render_template(
        "com.liftosaur.garmin-watcher.plist.template",
        {
            "profile_name": profile_name,
            "watcher_script_path": script_path,
            "poll_interval": resolved_interval,
            "profile_dir": profile_dir,
        },
    )
    plist_path = Path(
        f"~/Library/LaunchAgents/com.liftosaur.garmin-watcher.{profile_name}.plist"
    ).expanduser()
    plist_path.write_text(plist_content, encoding="utf-8")

    subprocess.run([
        "launchctl",
        "unload",
        str(plist_path),
    ], capture_output=True, text=True)
    subprocess.run([
        "launchctl",
        "load",
        str(plist_path),
    ], check=True)

    print("✅ File watcher installed and running")
    return True


def _install_systemd(
    profile_name: str,
    profile_dir: Path,
    watch_dir: Path,
    python_path: str,
) -> bool:
    if not shutil.which("inotifywait"):
        print(
            "⚠️  inotifywait not found. Install inotify-tools: "
            "sudo apt install inotify-tools"
        )
        return False

    profile_dir.mkdir(parents=True, exist_ok=True)
    script_path = profile_dir / "watch_and_process.sh"
    script_content = render_template(
        "watch_and_process.sh.template",
        {
            "watch_dir": watch_dir,
            "python_path": python_path,
            "profile_name": profile_name,
            "log_file": profile_dir / "watcher.log",
            "processed_file": profile_dir / "processed_files.txt",
        },
    )
    script_path.write_text(script_content, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    service_dir = Path("~/.config/systemd/user").expanduser()
    service_dir.mkdir(parents=True, exist_ok=True)
    service_path = service_dir / f"liftosaur-garmin-{profile_name}.service"
    service_content = (
        "[Unit]\n"
        f"Description=Liftosaur Garmin Watcher ({profile_name})\n\n"
        "[Service]\n"
        "Type=simple\n"
        "ExecStart=/bin/bash -c 'while inotifywait -e create -e moved_to "
        f"\"{watch_dir}\"; do {script_path}; done'\n"
        "Restart=on-failure\n"
        "RestartSec=5\n\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )
    service_path.write_text(service_content, encoding="utf-8")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(
        [
            "systemctl",
            "--user",
            "enable",
            "--now",
            f"liftosaur-garmin-{profile_name}.service",
        ],
        check=True,
    )

    print("✅ File watcher installed and running (systemd)")
    return True


def uninstall_watcher(profile_name: str, profile_dir: Path) -> bool:
    """Uninstall a watcher for the current OS."""
    system = platform.system()
    if system == "Darwin":
        plist_path = Path(
            f"~/Library/LaunchAgents/com.liftosaur.garmin-watcher.{profile_name}.plist"
        ).expanduser()
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
            text=True,
        )
        if plist_path.exists():
            plist_path.unlink()
        script_path = profile_dir / "watch_and_process.sh"
        if script_path.exists():
            script_path.unlink()
        print("✅ File watcher uninstalled")
        return True

    if system == "Linux":
        service_path = Path(
            f"~/.config/systemd/user/liftosaur-garmin-{profile_name}.service"
        ).expanduser()
        subprocess.run(
            [
                "systemctl",
                "--user",
                "disable",
                "--now",
                f"liftosaur-garmin-{profile_name}.service",
            ],
            capture_output=True,
            text=True,
        )
        if service_path.exists():
            service_path.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        print("✅ File watcher uninstalled")
        return True

    print(
        "⚠️  Automatic file watching is not yet supported on Windows. "
        "You can run the tool manually or set up Task Scheduler."
    )
    return False


def watcher_status(profile_name: str) -> str:
    """Return watcher status: running, installed, or not installed."""
    system = platform.system()
    if system == "Darwin":
        label = f"com.liftosaur.garmin-watcher.{profile_name}"
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and label in result.stdout:
            return "running"
        plist_path = Path(
            f"~/Library/LaunchAgents/com.liftosaur.garmin-watcher.{profile_name}.plist"
        ).expanduser()
        if plist_path.exists():
            return "installed"
        return "not installed"

    if system == "Linux":
        service_name = f"liftosaur-garmin-{profile_name}.service"
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service_name],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip() == "active":
            return "running"
        service_path = Path(
            f"~/.config/systemd/user/liftosaur-garmin-{profile_name}.service"
        ).expanduser()
        if service_path.exists():
            return "installed"
        return "not installed"

    return "not installed"
