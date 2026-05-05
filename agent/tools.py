import subprocess
from pathlib import Path


SOUNDS_DIR = "sounds"
FALLBACK_SOUND = "/System/Library/Sounds/Funk.aiff"


def play_sound_impl(sound_type: str, sounds_dir: str = SOUNDS_DIR) -> str:
    sounds_path = Path(sounds_dir)
    candidates = list(sounds_path.glob(f"{sound_type}.*"))

    if candidates:
        sound_file = str(candidates[0])
        subprocess.run(["afplay", sound_file], check=True, timeout=10)
        return f"Played sound: {sound_type} ({candidates[0].name})"
    else:
        subprocess.run(["afplay", FALLBACK_SOUND], check=True, timeout=10)
        return f"Played fallback sound (Funk.aiff) — no file found for '{sound_type}'"


def notify_owner_impl(title: str, message: str) -> str:
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], check=True, timeout=5)
    return f"Sent notification: [{title}] {message}"
