import json
import tempfile
from pathlib import Path

from activities.logger import log_event


def test_log_event_writes_jsonl(tmp_path):
    log_file = tmp_path / "events.jsonl"

    log_event(
        summary="Bird detected on railing",
        photo_path="/photos/bird.jpg",
        actions_taken=["play_sound:bird_scare"],
        log_file=str(log_file),
    )

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["summary"] == "Bird detected on railing"
    assert entry["photo_path"] == "/photos/bird.jpg"
    assert entry["actions_taken"] == ["play_sound:bird_scare"]
    assert "timestamp" in entry


def test_log_event_appends(tmp_path):
    log_file = tmp_path / "events.jsonl"

    log_event("First", "/photos/a.jpg", [], str(log_file))
    log_event("Second", "/photos/b.jpg", ["notify"], str(log_file))

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 2
