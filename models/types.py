from dataclasses import dataclass


@dataclass
class CapturedPhoto:
    path: str
    data_b64: str  # base64-encoded image bytes
    media_type: str


@dataclass
class MonitorConfig:
    photos_dir: str = "photos"
    interval_seconds: int = 30
    continue_as_new_threshold: int = 100
    num_cycles: int = 0  # 0 = infinite, >0 = stop after N cycles


@dataclass
class TerraceStatus:
    last_photo_path: str | None
    last_analysis: str | None
    last_checked_at: str | None
    is_paused: bool
    interval_seconds: int
    cycle_count: int
