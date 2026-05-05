import base64
from pathlib import Path

from temporalio import activity

from models.types import CapturedPhoto

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}

_photo_index: dict[str, int] = {}


@activity.defn
def capture_photo(photos_dir: str) -> CapturedPhoto:
    path = Path(photos_dir)
    files = sorted(
        f for f in path.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not files:
        raise FileNotFoundError(f"No image files found in {photos_dir}")

    idx = _photo_index.get(photos_dir, 0)
    photo = files[idx % len(files)]
    _photo_index[photos_dir] = (idx + 1) % len(files)

    activity.logger.info(f"Captured photo: {photo.name} ({idx % len(files) + 1}/{len(files)})")
    return CapturedPhoto(
        path=str(photo),
        data_b64=base64.b64encode(photo.read_bytes()).decode("ascii"),
        media_type=MEDIA_TYPES.get(photo.suffix.lower(), "image/jpeg"),
    )
