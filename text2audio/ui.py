"""
UI module for text2audio package.

Contains progress bars, console output, and audio playback functionality.
"""

import sys
import shutil
import subprocess
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

# Optional Rich progress UI
HAS_RICH = True
try:
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, BarColumn
    from rich.console import Console
except Exception:
    HAS_RICH = False
    Console = None


@contextmanager
def progress_context(description: str = "Processing...", total: Optional[int] = None):
    """
    Context manager for Rich progress bars with fallback to plain output.
    
    Args:
        description: Task description
        total: Total number of items (None for indeterminate progress)
        
    Yields:
        Progress instance or None if Rich not available
    """
    if HAS_RICH:
        console = Console()
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn() if total else "",
            TimeElapsedColumn(),
            transient=True,
            console=console,
        ) as progress:
            yield progress
    else:
        print(f"{description}")
        yield None


def simple_progress_task(description: str):
    """Simple progress indicator without Rich."""
    if HAS_RICH:
        console = Console()
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            TimeElapsedColumn(),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task(description, total=None)
            yield progress, task
    else:
        print(f"{description}")
        yield None, None


def _select_player_cmd(audio_path: Path):
    """Return a list suitable for subprocess to play audio on macOS/Linux, or None if not found."""
    ext = audio_path.suffix.lower().lstrip(".")
    platform = sys.platform
    
    # macOS: afplay is standard
    if platform == "darwin":
        if shutil.which("afplay"):
            return ["afplay", str(audio_path)]
        # Fallbacks on mac if present
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_path)]
        if shutil.which("mpv"):
            return ["mpv", "--no-video", "--really-quiet", str(audio_path)]
        if shutil.which("vlc"):
            return ["vlc", "--intf", "dummy", "--play-and-exit", "--quiet", str(audio_path)]
        return None
        
    # Linux
    if platform.startswith("linux"):
        # Prefer ffplay/mpv/vlc/mplayer
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_path)]
        if shutil.which("mpv"):
            return ["mpv", "--no-video", "--really-quiet", str(audio_path)]
        if shutil.which("vlc"):
            return ["vlc", "--intf", "dummy", "--play-and-exit", "--quiet", str(audio_path)]
        if shutil.which("mplayer"):
            return ["mplayer", "-really-quiet", str(audio_path)]
        # Format-specific fallbacks
        if ext in {"mp3", "aac", "opus"} and shutil.which("mpg123"):
            return ["mpg123", "-q", str(audio_path)]
        if ext in {"wav"} and shutil.which("aplay"):
            return ["aplay", str(audio_path)]
        if shutil.which("paplay"):
            return ["paplay", str(audio_path)]
        if shutil.which("play"):
            return ["play", "-q", str(audio_path)]
        return None
        
    # Ignore Windows per requirements
    return None


def play_audio_file(audio_path: Path) -> int:
    """
    Play an audio file using available system players.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        Return code from the player (0 for success)
    """
    cmd = _select_player_cmd(audio_path)
    if not cmd:
        print("No suitable audio player found for your OS/path. Skipping playback.")
        return 1
        
    if HAS_RICH:
        console = Console()
        eq_frames = [
            "▁▂▃▄▅▆▇▆▅▄▃▂",
            "▂▃▄▅▆▇▆▅▄▃▂▁",
            "▃▄▅▆▇▆▅▄▃▂▁▂",
            "▄▅▆▇▆▅▄▃▂▁▂▃",
            "▅▆▇▆▅▄▃▂▁▂▃▄",
            "▆▇▆▅▄▃▂▁▂▃▄▅",
            "▇▆▅▄▃▂▁▂▃▄▅▆",
            "▆▅▄▃▂▁▂▃▄▅▆▇",
            "▅▄▃▂▁▂▃▄▅▆▇▆",
            "▄▃▂▁▂▃▄▅▆▇▆▅",
            "▃▂▁▂▃▄▅▆▇▆▅▄",
            "▂▁▂▃▄▅▆▇▆▅▄▃",
        ]
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            TimeElapsedColumn(),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("Playing audio…", total=None)
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            i = 0
            while proc.poll() is None:
                frame = eq_frames[i % len(eq_frames)]
                progress.update(task, description=f"Playing audio {frame}")
                time.sleep(0.15)
                i += 1
            progress.stop_task(task)
        return proc.returncode or 0
    else:
        print("Playing audio…")
        try:
            return subprocess.call(cmd)
        finally:
            print("Playback finished.")