"""Locate the separately maintained AudioToLyrics application on Windows."""

import os
import sys
from pathlib import Path


INSTALLER_NAME = 'AudioToLyrics-v5.2.0-setup.exe'


def application_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def bundled_installer() -> Path | None:
    candidate = application_root() / 'Tools' / INSTALLER_NAME
    return candidate if candidate.is_file() else None


def find_audio_to_lyrics() -> Path | None:
    """Return a launchable shortcut or executable, without changing the tool."""
    root = application_root()
    candidates = [
        root / 'Tools' / 'AudioToLyrics' / 'AudioToLyrics.exe',
        Path(os.environ['AUDIO_TO_LYRICS_EXE']) if os.environ.get('AUDIO_TO_LYRICS_EXE') else None,
        Path(os.environ.get('PUBLIC', r'C:\Users\Public')) / 'Desktop' / 'AudioToLyrics.lnk',
        Path.home() / 'Desktop' / 'AudioToLyrics.lnk',
    ]
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for subkey in (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
                           r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'):
                try:
                    with winreg.OpenKey(hive, subkey) as parent:
                        for index in range(winreg.QueryInfoKey(parent)[0]):
                            with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as entry:
                                try:
                                    name = str(winreg.QueryValueEx(entry, 'DisplayName')[0])
                                    location = str(winreg.QueryValueEx(entry, 'InstallLocation')[0])
                                except OSError:
                                    continue
                                if 'audiotolyrics' in name.lower() and location:
                                    candidates.append(Path(location) / 'AudioToLyrics.exe')
                except OSError:
                    continue
    except ImportError:
        pass
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    return None


def launch(path: Path) -> None:
    if path.suffix.lower() == '.lnk':
        os.startfile(str(path))
    else:
        import subprocess
        subprocess.Popen([str(path)], cwd=str(path.parent))
