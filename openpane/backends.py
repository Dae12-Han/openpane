"""
openpane.backends
Platform-specific terminal background control.

Currently supported:
- macOS  → iTerm2  (animated GIF via AppleScript)
- Windows → Windows Terminal (static PNG via settings.json)
"""

import os
import json
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Optional


# ── Platform detection ──────────────────────────────────────
def detect_platform() -> str:
    """Return one of: 'macos-iterm2', 'windows-terminal', 'unsupported'."""
    system = platform.system()

    if system == "Darwin":
        if os.environ.get("TERM_PROGRAM") == "iTerm.app":
            return "macos-iterm2"
        return "macos-other"

    if system == "Windows":
        # Windows Terminal sets WT_SESSION
        if os.environ.get("WT_SESSION"):
            return "windows-terminal"
        return "windows-other"

    return "unsupported"


# ── Backend protocol ────────────────────────────────────────
class Backend:
    """Abstract interface for terminal background backends."""

    name = "base"
    image_format = "gif"   # 'gif' or 'png'

    def apply(self, image_path: Path) -> bool:
        raise NotImplementedError

    def clear(self) -> bool:
        raise NotImplementedError


# ── macOS / iTerm2 ──────────────────────────────────────────
class ITerm2Backend(Backend):
    """Set iTerm2 background image via AppleScript."""

    name = "iTerm2"
    image_format = "gif"

    def apply(self, image_path: Path) -> bool:
        safe_path = str(image_path).replace('"', '\\"')
        script = f'''
        tell application "iTerm"
            tell current session of current window
                set background image to "{safe_path}"
            end tell
        end tell
        '''
        return self._run_osascript(script)

    def clear(self) -> bool:
        script = '''
        tell application "iTerm"
            tell current session of current window
                set background image to ""
            end tell
        end tell
        '''
        return self._run_osascript(script)

    @staticmethod
    def _run_osascript(script: str) -> bool:
        try:
            subprocess.run(
                ["osascript", "-e", script],
                check=True, capture_output=True, timeout=5,
            )
            return True
        except Exception:
            return False


# ── Windows / Windows Terminal ──────────────────────────────
class WindowsTerminalBackend(Backend):
    """
    Set Windows Terminal background image by editing settings.json.

    Windows Terminal stores per-profile settings in a JSON file. We update
    the active profile's `backgroundImage` field. The change takes effect
    immediately — Windows Terminal watches the file and reloads.
    """

    name = "Windows Terminal"
    image_format = "png"   # WT does not animate GIFs

    def apply(self, image_path: Path) -> bool:
        try:
            settings_path = self._settings_path()
            data = self._read(settings_path)
            self._set_active_background(data, str(image_path))
            self._write(settings_path, data)
            return True
        except Exception:
            return False

    def clear(self) -> bool:
        try:
            settings_path = self._settings_path()
            data = self._read(settings_path)
            self._set_active_background(data, None)
            self._write(settings_path, data)
            return True
        except Exception:
            return False

    @staticmethod
    def _settings_path() -> Path:
        """Locate Windows Terminal's settings.json (Stable or Preview)."""
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise RuntimeError("LOCALAPPDATA not set")

        candidates = [
            Path(local_app_data) / "Packages" /
                "Microsoft.WindowsTerminal_8wekyb3d8bbwe" / "LocalState" / "settings.json",
            Path(local_app_data) / "Packages" /
                "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe" / "LocalState" / "settings.json",
        ]
        for p in candidates:
            if p.exists():
                return p
        raise FileNotFoundError("Windows Terminal settings.json not found")

    @staticmethod
    def _read(path: Path) -> dict:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    @staticmethod
    def _write(path: Path, data: dict):
        # Backup once
        backup = path.with_suffix(".json.openpane-backup")
        if not backup.exists():
            shutil.copy2(path, backup)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def _set_active_background(data: dict, image_path: Optional[str]):
        """Update backgroundImage on the default profile (or all profiles)."""
        profiles = data.get("profiles", {})
        # profiles can be either a list or a {"defaults": ..., "list": [...]} dict
        if isinstance(profiles, dict):
            defaults = profiles.setdefault("defaults", {})
            target = defaults
        else:
            # Legacy format: list of profiles, set on first (active) one
            target = profiles[0] if profiles else {}

        if image_path is None:
            target.pop("backgroundImage", None)
            target.pop("backgroundImageOpacity", None)
            target.pop("backgroundImageStretchMode", None)
        else:
            target["backgroundImage"] = image_path
            target["backgroundImageOpacity"] = 0.6
            target["backgroundImageStretchMode"] = "uniformToFill"


# ── Backend resolver ────────────────────────────────────────
def get_backend() -> Optional[Backend]:
    """Return a backend instance for the current environment, or None."""
    p = detect_platform()
    if p == "macos-iterm2":
        return ITerm2Backend()
    if p == "windows-terminal":
        return WindowsTerminalBackend()
    return None


def diagnose() -> str:
    """Human-readable explanation of the current environment."""
    p = detect_platform()
    return {
        "macos-iterm2":     "✅ macOS + iTerm2 detected",
        "macos-other":      "⚠️  macOS detected, but not iTerm2 (Terminal.app does not support background images)",
        "windows-terminal": "✅ Windows Terminal detected",
        "windows-other":    "⚠️  Windows detected, but not Windows Terminal (cmd / PowerShell consoles are not supported)",
        "unsupported":      "❌ unsupported platform — only macOS (iTerm2) and Windows (Windows Terminal) are supported",
    }[p]
