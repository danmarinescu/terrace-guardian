import base64
import os
import tempfile
from pathlib import Path

from activities.camera import capture_photo


def test_capture_photo_cycles_through_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        for name in ["a_bird.jpg", "b_plants.jpg", "c_rain.jpg"]:
            Path(tmpdir, name).write_bytes(b"fake image data")

        photo1 = capture_photo(tmpdir)
        assert os.path.basename(photo1.path) == "a_bird.jpg"
        assert base64.b64decode(photo1.data_b64) == b"fake image data"
        assert photo1.media_type == "image/jpeg"

        photo2 = capture_photo(tmpdir)
        assert os.path.basename(photo2.path) == "b_plants.jpg"

        photo3 = capture_photo(tmpdir)
        assert os.path.basename(photo3.path) == "c_rain.jpg"

        photo4 = capture_photo(tmpdir)
        assert os.path.basename(photo4.path) == "a_bird.jpg"


def test_capture_photo_filters_non_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "notes.txt").write_text("not an image")
        Path(tmpdir, "photo.png").write_bytes(b"fake png data")
        Path(tmpdir, ".gitkeep").write_text("")

        photo = capture_photo(tmpdir)
        assert os.path.basename(photo.path) == "photo.png"
        assert photo.media_type == "image/png"


def test_capture_photo_empty_dir_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            capture_photo(tmpdir)
            assert False, "Should have raised"
        except FileNotFoundError:
            pass
