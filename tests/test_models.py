from models.types import CapturedPhoto, MonitorConfig, TerraceStatus


def test_monitor_config_defaults():
    config = MonitorConfig()
    assert config.photos_dir == "photos"
    assert config.interval_seconds == 30
    assert config.continue_as_new_threshold == 100


def test_captured_photo():
    photo = CapturedPhoto(
        path="/photos/bird.jpg",
        data=b"fake image bytes",
        media_type="image/jpeg",
    )
    assert photo.path == "/photos/bird.jpg"
    assert photo.data == b"fake image bytes"
    assert photo.media_type == "image/jpeg"


def test_terrace_status_initial():
    status = TerraceStatus(
        last_photo_path=None,
        last_analysis=None,
        last_checked_at=None,
        is_paused=False,
        interval_seconds=30,
        cycle_count=0,
    )
    assert status.is_paused is False
    assert status.cycle_count == 0


def test_terrace_status_with_data():
    status = TerraceStatus(
        last_photo_path="/photos/bird.jpg",
        last_analysis="Bird detected on railing. Played scare sound.",
        last_checked_at="2026-05-05T10:30:00",
        is_paused=False,
        interval_seconds=60,
        cycle_count=5,
    )
    assert status.last_photo_path == "/photos/bird.jpg"
    assert "Bird" in status.last_analysis
