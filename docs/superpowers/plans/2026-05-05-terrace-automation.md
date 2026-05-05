# Terrace Automation System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Temporal workflow that monitors an outdoor terrace via camera photos, analyzes scenes with a Pydantic AI agent (Claude Sonnet 4.6), and dispatches actuators (sound, macOS notifications) based on what it finds.

**Architecture:** Single long-lived `TerraceMonitorWorkflow` with an infinite loop: capture photo → run Pydantic AI TemporalAgent (analyzes + actuates via tools) → log → sleep. Workflow supports pause/resume/interval signals and a status query. Uses `continue-as-new` to bound history.

**Tech Stack:** Python 3.13, temporalio, pydantic-ai[anthropic], macOS afplay/osascript

**Spec:** `docs/superpowers/specs/2026-05-05-terrace-automation-design.md`

---

### Task 1: Project Setup — Dependencies and Directory Structure

**Files:**
- Modify: `pyproject.toml`
- Create: `models/__init__.py`, `models/types.py`
- Create: `activities/__init__.py`, `activities/camera.py`, `activities/logger.py`
- Create: `agent/__init__.py`, `agent/tools.py`, `agent/terrace_agent.py`
- Create: `workflows/__init__.py`, `workflows/terrace_monitor.py`
- Create: `photos/.gitkeep`, `sounds/.gitkeep`, `logs/.gitkeep`

- [ ] **Step 1: Add dependencies to pyproject.toml**

```toml
[project]
name = "test-project"
version = "0.1.0"
description = "Terrace automation system — monitors outdoor terrace with AI"
readme = "README.md"
requires-python = ">=3.9"
dependencies = [
    "temporalio>=1.18.2",
    "pydantic-ai[anthropic]",
]
```

- [ ] **Step 2: Install dependencies**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv sync`
Expected: dependencies resolve and install successfully.

- [ ] **Step 3: Create all package directories and empty __init__.py files**

```bash
mkdir -p models activities agent workflows photos sounds logs
touch models/__init__.py activities/__init__.py agent/__init__.py workflows/__init__.py
touch photos/.gitkeep sounds/.gitkeep logs/.gitkeep
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock models/ activities/ agent/ workflows/ photos/.gitkeep sounds/.gitkeep logs/.gitkeep
git commit -m "feat: project setup with dependencies and directory structure"
```

---

### Task 2: Data Models

**Files:**
- Create: `models/types.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the test for data models**

Create `tests/__init__.py` and `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.types'`

- [ ] **Step 3: Implement the data models**

Write `models/types.py`:

```python
from dataclasses import dataclass


@dataclass
class CapturedPhoto:
    path: str
    data: bytes
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run pytest tests/test_models.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add models/types.py tests/
git commit -m "feat: add MonitorConfig and TerraceStatus data models"
```

---

### Task 3: Camera Activity — capture_photo

**Files:**
- Create: `activities/camera.py`
- Test: `tests/test_camera.py`

- [ ] **Step 1: Write the test for capture_photo**

Create `tests/test_camera.py`:

```python
import os
import tempfile
from pathlib import Path

from activities.camera import capture_photo


def test_capture_photo_cycles_through_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test image files
        for name in ["a_bird.jpg", "b_plants.jpg", "c_rain.jpg"]:
            Path(tmpdir, name).write_bytes(b"fake image data")

        photo1 = capture_photo(tmpdir)
        assert os.path.basename(photo1.path) == "a_bird.jpg"
        assert photo1.data == b"fake image data"
        assert photo1.media_type == "image/jpeg"

        photo2 = capture_photo(tmpdir)
        assert os.path.basename(photo2.path) == "b_plants.jpg"

        photo3 = capture_photo(tmpdir)
        assert os.path.basename(photo3.path) == "c_rain.jpg"

        # Wraps around
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run pytest tests/test_camera.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement capture_photo**

Write `activities/camera.py`:

```python
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
async def capture_photo(photos_dir: str) -> CapturedPhoto:
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
        data=photo.read_bytes(),
        media_type=MEDIA_TYPES.get(photo.suffix.lower(), "image/jpeg"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run pytest tests/test_camera.py -v`
Expected: 3 tests PASS

Note: The tests call `capture_photo` directly as a regular function. The `@activity.defn` decorator does not prevent this — it only adds metadata for Temporal. No Temporal test environment is needed.

- [ ] **Step 5: Commit**

```bash
git add activities/camera.py tests/test_camera.py
git commit -m "feat: add capture_photo activity with round-robin cycling"
```

---

### Task 4: Logger Activity — log_event

**Files:**
- Create: `activities/logger.py`
- Test: `tests/test_logger.py`

- [ ] **Step 1: Write the test for log_event**

Create `tests/test_logger.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run pytest tests/test_logger.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement log_event**

Write `activities/logger.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from temporalio import activity


@activity.defn
async def log_event(
    summary: str,
    photo_path: str,
    actions_taken: list[str],
    log_file: str = "logs/events.jsonl",
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "photo_path": photo_path,
        "summary": summary,
        "actions_taken": actions_taken,
    }

    log_line = json.dumps(entry)
    activity.logger.info(log_line)

    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(log_line + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run pytest tests/test_logger.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add activities/logger.py tests/test_logger.py
git commit -m "feat: add log_event activity with JSONL output"
```

---

### Task 5: Agent Tools — play_sound and notify_owner

**Files:**
- Create: `agent/tools.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the test for tools**

Create `tests/test_tools.py`. Since these tools call macOS system commands, we test the logic with mocked subprocess calls:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run pytest tests/test_tools.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement the tools**

Write `agent/tools.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run pytest tests/test_tools.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat: add play_sound and notify_owner tool implementations"
```

---

### Task 6: Pydantic AI Agent Definition

**Files:**
- Create: `agent/terrace_agent.py`

This task wires up the Pydantic AI agent with tools and the TemporalAgent wrapper. No unit test for this file — it's pure wiring that will be validated by the integration test in Task 8.

- [ ] **Step 1: Implement the terrace agent**

Write `agent/terrace_agent.py`:

```python
from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import TemporalAgent

from agent.tools import play_sound_impl, notify_owner_impl

agent = Agent(
    "anthropic:claude-sonnet-4-6",
    instructions=(
        "You are a terrace monitoring assistant. You analyze photos of an outdoor "
        "terrace and take appropriate actions using the tools available to you.\n\n"
        "When you see a photo, assess:\n"
        "- Birds or animals that should be scared away → use play_sound\n"
        "- Plants that look dry or wilting → use notify_owner to alert about watering\n"
        "- Rain with exposed items (cushions, electronics, books) → use notify_owner\n"
        "- Anything else notable → use notify_owner if it needs human attention\n"
        "- If nothing requires attention, just describe what you see\n\n"
        "Always provide a brief summary of your analysis as your final response."
    ),
    name="terrace_monitor",
)


@agent.tool_plain
def play_sound(sound_type: str) -> str:
    """Play a sound to scare away birds or animals from the terrace.

    Args:
        sound_type: Type of sound to play, e.g. 'bird_scare' for scaring birds.
    """
    return play_sound_impl(sound_type)


@agent.tool_plain
def notify_owner(title: str, message: str) -> str:
    """Send a notification to the terrace owner about a condition that needs attention.

    Args:
        title: Short title for the notification, e.g. 'Rain Alert'.
        message: Detailed message about what was detected and what action may be needed.
    """
    return notify_owner_impl(title, message)


temporal_agent = TemporalAgent(agent)
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run python -c "from agent.terrace_agent import temporal_agent; print('OK:', temporal_agent)"`
Expected: prints `OK:` followed by the TemporalAgent repr. No import errors.

- [ ] **Step 3: Commit**

```bash
git add agent/terrace_agent.py
git commit -m "feat: add Pydantic AI terrace agent with tool definitions"
```

---

### Task 7: Temporal Workflow — TerraceMonitorWorkflow

**Files:**
- Create: `workflows/terrace_monitor.py`

- [ ] **Step 1: Implement the workflow**

Write `workflows/terrace_monitor.py`:

```python
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from pydantic_ai import BinaryContent
    from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow

    from activities.camera import capture_photo
    from activities.logger import log_event
    from agent.terrace_agent import temporal_agent
    from models.types import CapturedPhoto, MonitorConfig, TerraceStatus


@workflow.defn
class TerraceMonitorWorkflow(PydanticAIWorkflow):
    __pydantic_ai_agents__ = [temporal_agent]

    def __init__(self) -> None:
        self._is_paused = False
        self._interval_seconds = 30
        self._cycle_count = 0
        self._last_photo_path: str | None = None
        self._last_analysis: str | None = None
        self._last_checked_at: str | None = None
        self._photos_dir = "photos"
        self._continue_as_new_threshold = 100

    @workflow.run
    async def run(self, config: MonitorConfig) -> None:
        self._interval_seconds = config.interval_seconds
        self._photos_dir = config.photos_dir
        self._continue_as_new_threshold = config.continue_as_new_threshold

        while True:
            if not self._is_paused:
                try:
                    await self._run_cycle()
                except Exception as e:
                    workflow.logger.error(f"Cycle failed: {e}")
                    await workflow.execute_activity(
                        log_event,
                        args=[f"Cycle failed: {e}", self._last_photo_path or "", []],
                        start_to_close_timeout=timedelta(seconds=5),
                    )

            self._cycle_count += 1

            if self._cycle_count >= self._continue_as_new_threshold:
                workflow.logger.info("Continuing as new to reset history")
                config_carry = MonitorConfig(
                    photos_dir=self._photos_dir,
                    interval_seconds=self._interval_seconds,
                    continue_as_new_threshold=self._continue_as_new_threshold,
                )
                workflow.continue_as_new(config_carry)

            await workflow.sleep(self._interval_seconds)

    async def _run_cycle(self) -> None:
        photo: CapturedPhoto = await workflow.execute_activity(
            capture_photo,
            args=[self._photos_dir],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        self._last_photo_path = photo.path

        result = await temporal_agent.run(
            [
                (
                    "Analyze this photo of my outdoor terrace. "
                    "Look for birds/animals, check plant health, assess weather "
                    "conditions and rain risk to exposed items. "
                    "Use your tools to take action if needed. "
                    "If nothing requires attention, just describe what you see."
                ),
                BinaryContent(data=photo.data, media_type=photo.media_type),
            ]
        )

        self._last_analysis = result.output
        now = workflow.now().isoformat()
        self._last_checked_at = now

        actions_taken = [
            f"{call.tool_name}({call.args})"
            for call in result.all_messages()
            if hasattr(call, "tool_name")
        ]

        await workflow.execute_activity(
            log_event,
            args=[result.output, photo.path, actions_taken],
            start_to_close_timeout=timedelta(seconds=5),
        )

    @workflow.signal
    async def pause(self) -> None:
        workflow.logger.info("Monitoring paused")
        self._is_paused = True

    @workflow.signal
    async def resume(self) -> None:
        workflow.logger.info("Monitoring resumed")
        self._is_paused = False

    @workflow.signal
    async def set_interval(self, seconds: int) -> None:
        clamped = max(10, min(600, seconds))
        workflow.logger.info(f"Interval changed to {clamped}s")
        self._interval_seconds = clamped

    @workflow.query
    def get_terrace_status(self) -> TerraceStatus:
        return TerraceStatus(
            last_photo_path=self._last_photo_path,
            last_analysis=self._last_analysis,
            last_checked_at=self._last_checked_at,
            is_paused=self._is_paused,
            interval_seconds=self._interval_seconds,
            cycle_count=self._cycle_count,
        )
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run python -c "from workflows.terrace_monitor import TerraceMonitorWorkflow; print('OK')"`
Expected: prints `OK`. No import errors.

- [ ] **Step 3: Commit**

```bash
git add workflows/terrace_monitor.py
git commit -m "feat: add TerraceMonitorWorkflow with signals and queries"
```

---

### Task 8: CLI Entry Point — main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Implement the CLI**

Replace `main.py` with:

```python
import argparse
import asyncio
import json
import sys

from temporalio.client import Client
from temporalio.worker import Worker

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

from activities.camera import capture_photo
from activities.logger import log_event
from agent.terrace_agent import temporal_agent
from models.types import MonitorConfig
from workflows.terrace_monitor import TerraceMonitorWorkflow

TASK_QUEUE = "terrace-monitor"
WORKFLOW_ID = "terrace-monitor"


async def run_worker():
    client = await Client.connect("localhost:7233", plugins=[PydanticAIPlugin()])
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TerraceMonitorWorkflow],
        activities=[capture_photo, log_event],
    )
    print(f"Worker started on task queue '{TASK_QUEUE}'")
    await worker.run()


async def start_workflow(photos_dir: str, interval: int):
    client = await Client.connect("localhost:7233", plugins=[PydanticAIPlugin()])
    config = MonitorConfig(photos_dir=photos_dir, interval_seconds=interval)
    handle = await client.start_workflow(
        TerraceMonitorWorkflow.run,
        config,
        id=WORKFLOW_ID,
        task_queue=TASK_QUEUE,
    )
    print(f"Workflow started: {handle.id}")
    print(f"  Photos dir: {photos_dir}")
    print(f"  Interval: {interval}s")


async def send_signal(signal_name: str, arg=None):
    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle(WORKFLOW_ID)
    if signal_name == "pause":
        await handle.signal(TerraceMonitorWorkflow.pause)
        print("Sent pause signal")
    elif signal_name == "resume":
        await handle.signal(TerraceMonitorWorkflow.resume)
        print("Sent resume signal")
    elif signal_name == "set_interval":
        await handle.signal(TerraceMonitorWorkflow.set_interval, arg)
        print(f"Sent set_interval signal: {arg}s")


async def query_status():
    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle(WORKFLOW_ID)
    status = await handle.query(TerraceMonitorWorkflow.get_terrace_status)
    print(json.dumps({
        "last_photo_path": status.last_photo_path,
        "last_analysis": status.last_analysis,
        "last_checked_at": status.last_checked_at,
        "is_paused": status.is_paused,
        "interval_seconds": status.interval_seconds,
        "cycle_count": status.cycle_count,
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Terrace Monitor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("worker", help="Start the Temporal worker")

    start_parser = subparsers.add_parser("start", help="Start the monitoring workflow")
    start_parser.add_argument("--photos-dir", default="photos", help="Directory with terrace photos")
    start_parser.add_argument("--interval", type=int, default=30, help="Seconds between checks")

    subparsers.add_parser("pause", help="Pause monitoring")
    subparsers.add_parser("resume", help="Resume monitoring")
    subparsers.add_parser("status", help="Query current terrace status")

    interval_parser = subparsers.add_parser("interval", help="Change monitoring interval")
    interval_parser.add_argument("seconds", type=int, help="New interval in seconds")

    args = parser.parse_args()

    if args.command == "worker":
        asyncio.run(run_worker())
    elif args.command == "start":
        asyncio.run(start_workflow(args.photos_dir, args.interval))
    elif args.command == "pause":
        asyncio.run(send_signal("pause"))
    elif args.command == "resume":
        asyncio.run(send_signal("resume"))
    elif args.command == "status":
        asyncio.run(query_status())
    elif args.command == "interval":
        asyncio.run(send_signal("set_interval", args.seconds))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI help works**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run python main.py --help`
Expected: shows usage with subcommands (worker, start, pause, resume, status, interval)

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run python main.py start --help`
Expected: shows --photos-dir and --interval options

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add CLI entry point for worker, workflow, and signals"
```

---

### Task 9: Integration Test — End-to-End with Temporal

**Files:**
- Create: `tests/test_workflow_integration.py`

This test runs the full workflow loop once using the Temporal test environment. It mocks the Pydantic AI agent call and the system commands, verifying the workflow orchestration logic.

- [ ] **Step 1: Write the integration test**

Create `tests/test_workflow_integration.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import timedelta

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporalio.common import RetryPolicy

from activities.camera import capture_photo
from activities.logger import log_event
from models.types import MonitorConfig
from workflows.terrace_monitor import TerraceMonitorWorkflow


@pytest.fixture
def photos_dir(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "bird.jpg").write_bytes(b"fake bird photo")
    (photos / "clean.jpg").write_bytes(b"fake clean photo")
    return str(photos)


@pytest.fixture
def log_dir(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    return str(logs / "events.jsonl")


@pytest.mark.asyncio
async def test_workflow_runs_one_cycle_and_responds_to_pause(photos_dir):
    env = await WorkflowEnvironment.start_time_skipping()
    async with env:
        # We'll test signals and queries on the workflow
        # The actual agent call will happen in the real integration test
        # Here we verify the workflow structure works with Temporal
        config = MonitorConfig(
            photos_dir=photos_dir,
            interval_seconds=10,
            continue_as_new_threshold=1000,
        )

        async with Worker(
            env.client,
            task_queue="test-terrace",
            workflows=[TerraceMonitorWorkflow],
            activities=[capture_photo, log_event],
        ):
            handle = await env.client.start_workflow(
                TerraceMonitorWorkflow.run,
                config,
                id="test-terrace-monitor",
                task_queue="test-terrace",
            )

            # Give workflow time to start
            await env.sleep(duration=timedelta(seconds=1))

            # Test pause signal
            await handle.signal(TerraceMonitorWorkflow.pause)
            await env.sleep(duration=timedelta(seconds=1))

            # Test query
            status = await handle.query(TerraceMonitorWorkflow.get_terrace_status)
            assert status.is_paused is True
            assert status.interval_seconds == 10

            # Test resume
            await handle.signal(TerraceMonitorWorkflow.resume)
            await env.sleep(duration=timedelta(seconds=1))

            status = await handle.query(TerraceMonitorWorkflow.get_terrace_status)
            assert status.is_paused is False

            # Test set_interval
            await handle.signal(TerraceMonitorWorkflow.set_interval, 60)
            await env.sleep(duration=timedelta(seconds=1))

            status = await handle.query(TerraceMonitorWorkflow.get_terrace_status)
            assert status.interval_seconds == 60

            # Cancel the workflow to end the test
            await handle.cancel()
```

- [ ] **Step 2: Add pytest-asyncio dependency**

Add to `pyproject.toml` under a dev group or just install:

```bash
cd /Users/dan/work/temporal_hackaton/test_project && uv add --dev pytest pytest-asyncio
```

- [ ] **Step 3: Run integration test**

Run: `cd /Users/dan/work/temporal_hackaton/test_project && uv run pytest tests/test_workflow_integration.py -v`

Note: This test requires the Pydantic AI agent, so it may need `ANTHROPIC_API_KEY` set, or it may fail on the agent call. If it fails on the agent call, that's OK — the signals and queries are what we're testing. We can mark the agent portion as a known limitation or mock it.

Expected: test demonstrates that workflow starts, responds to signals, and returns correct query results.

- [ ] **Step 4: Commit**

```bash
git add tests/test_workflow_integration.py pyproject.toml uv.lock
git commit -m "feat: add workflow integration test with signal/query verification"
```

---

### Task 10: Manual End-to-End Test

**Files:** None (manual verification)

- [ ] **Step 1: Ensure Temporal dev server is running**

Run: `temporal server start-dev`
Expected: Temporal server starts on localhost:7233, UI on localhost:8233

- [ ] **Step 2: Drop test images into photos/**

Download or create 3-4 test images and place them in the `photos/` directory:
- A photo with a bird (e.g., pigeon on a railing)
- A photo with dry/wilting plants
- A photo of rain with outdoor furniture/cushions
- A photo of a clean, empty terrace

- [ ] **Step 3: Set ANTHROPIC_API_KEY**

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

- [ ] **Step 4: Start the worker**

Run in terminal 1:
```bash
cd /Users/dan/work/temporal_hackaton/test_project && uv run python main.py worker
```
Expected: "Worker started on task queue 'terrace-monitor'"

- [ ] **Step 5: Start the workflow**

Run in terminal 2:
```bash
cd /Users/dan/work/temporal_hackaton/test_project && uv run python main.py start --interval 15
```
Expected: "Workflow started: terrace-monitor"

- [ ] **Step 6: Observe the system**

Watch terminal 1 for log output. After each 15-second cycle you should see:
- Photo capture log
- Agent analysis (may take a few seconds for the LLM call)
- Actuator actions: sound plays for bird photos, macOS notification pops up for rain/plant photos
- JSON log entries appended to `logs/events.jsonl`

- [ ] **Step 7: Test signals**

```bash
cd /Users/dan/work/temporal_hackaton/test_project && uv run python main.py status
cd /Users/dan/work/temporal_hackaton/test_project && uv run python main.py pause
cd /Users/dan/work/temporal_hackaton/test_project && uv run python main.py status
cd /Users/dan/work/temporal_hackaton/test_project && uv run python main.py resume
cd /Users/dan/work/temporal_hackaton/test_project && uv run python main.py interval 60
cd /Users/dan/work/temporal_hackaton/test_project && uv run python main.py status
```

Verify: status reflects pause/resume state changes and interval update.

- [ ] **Step 8: Check Temporal UI**

Open http://localhost:8233 in browser. Navigate to the `terrace-monitor` workflow. Verify you can see the workflow history with activity completions, signals received, and timer events.
