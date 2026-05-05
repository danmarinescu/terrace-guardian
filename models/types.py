from dataclasses import dataclass


@dataclass
class CapturedPhoto:
    path: str
    media_type: str


@dataclass
class MonitorConfig:
    photos_dir: str = "photos"
    interval_seconds: int = 30
    continue_as_new_threshold: int = 100


@dataclass
class TerraceStatus:
    last_photo_path: str | None
    last_analysis: str | None
    last_checked_at: str | None
    is_paused: bool
    interval_seconds: int
    cycle_count: int
