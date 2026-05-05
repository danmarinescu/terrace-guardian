from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

from agent.tools import play_sound_impl, notify_owner_impl


def test_play_sound_with_custom_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        sound_file = Path(tmpdir) / "bird_scare.wav"
        sound_file.write_bytes(b"fake audio")

        with patch("agent.tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = play_sound_impl("bird_scare", sounds_dir=tmpdir)

        mock_run.assert_called_once_with(["afplay", str(sound_file)], check=True, timeout=10)
        assert "bird_scare" in result


def test_play_sound_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("agent.tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = play_sound_impl("nonexistent", sounds_dir=tmpdir)

        call_args = mock_run.call_args[0][0]
        assert "/System/Library/Sounds/Funk.aiff" in call_args[1]
        assert "fallback" in result.lower() or "Funk" in result


def test_notify_owner():
    with patch("agent.tools.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = notify_owner_impl("Rain Alert", "Cushions getting wet")

    call_args = mock_run.call_args[0][0]
    assert "osascript" in call_args[0]
    assert "Rain Alert" in result or "notification" in result.lower()
