# Terrace Automation System — Design Spec

## Overview

An outdoor terrace monitoring and automation system built on Temporal workflows. A camera sensor captures photos at configurable intervals, Claude Sonnet 4.6 analyzes the scene via vision API, and the system dispatches actuators based on detected conditions (birds, dry plants, rain exposure, etc.).

## Architecture

Single long-lived `TerraceMonitorWorkflow` running an infinite loop:

```
capture_photo → analyze_scene → decide actions → dispatch actuators → log → sleep(interval)
```

The workflow holds all monitoring state and responds to signals (pause/resume/set_interval) and queries (get_terrace_status). After a configurable number of cycles (default 100), it calls `continue-as-new` to keep history bounded, carrying over current state.

Workflow ID is fixed (`terrace-monitor`) to ensure only one instance runs at a time.

## Data Models

### SceneAnalysis

Returned by the LLM analysis activity.

```python
class ConditionType(str, Enum):
    BIRD = "bird"
    DRY_PLANTS = "dry_plants"
    RAIN_EXPOSURE = "rain_exposure"
    OTHER = "other"

class ActionType(str, Enum):
    PLAY_SOUND = "play_sound"
    NOTIFY = "notify"
    WATER_PLANTS = "water_plants"
    NONE = "none"

@dataclass
class DetectedCondition:
    type: ConditionType
    confidence: float  # 0-1
    description: str

@dataclass
class RecommendedAction:
    action_type: ActionType
    reason: str

@dataclass
class SceneAnalysis:
    summary: str
    conditions: list[DetectedCondition]
    recommended_actions: list[RecommendedAction]
```

### TerraceStatus

Returned by the `get_terrace_status` query.

```python
@dataclass
class TerraceStatus:
    last_photo_path: str | None
    last_analysis: SceneAnalysis | None
    last_checked_at: str | None  # ISO timestamp
    is_paused: bool
    interval_seconds: int
    cycle_count: int
```

## Activities

### capture_photo(photos_dir: str) -> str

Reads the next image file from the `photos/` directory, cycling alphabetically (round-robin). Returns the file path. Tracks position via a simple counter that wraps around.

- Retry: 1 attempt (no retry needed — local filesystem)
- Timeout: 10s

### analyze_scene(photo_path: str) -> SceneAnalysis

Reads the image file, sends it to Claude Sonnet 4.6 vision API with a system prompt instructing structured JSON output. Parses the response into a `SceneAnalysis` dataclass.

- Retry: up to 2 retries
- Start-to-close timeout: 30s
- The system prompt defines the JSON schema and instructs the LLM to assess: birds/animals, plant health/dryness, weather conditions, items at risk from rain, and any other notable conditions.

### play_sound(sound_type: str) -> None

Plays an audio file using macOS `afplay` command. Maps `sound_type` to a file in the `sounds/` directory (e.g., `bird_scare`). Falls back to system beep (`afplay /System/Library/Sounds/Funk.aiff`) if the file is not found.

- Retry: none
- Timeout: 10s

### notify_owner(title: str, message: str) -> None

Sends a macOS system notification via `osascript -e 'display notification "message" with title "title"'`. Used for conditions requiring human attention (rain exposure, plant health alerts).

- Retry: none
- Timeout: 5s

### log_event(event: dict) -> None

Writes a structured JSON log entry to console (stdout) and appends to `logs/events.jsonl`. Logs every cycle including "no action needed" so there's a full history.

- Retry: none
- Timeout: 5s

## Workflow: TerraceMonitorWorkflow

### Input Parameters

```python
@dataclass
class MonitorConfig:
    photos_dir: str = "photos"
    interval_seconds: int = 30
    continue_as_new_threshold: int = 100
```

### Signals

- **`pause`** — Sets `is_paused = True`. Loop continues but skips capture/analyze/actuate.
- **`resume`** — Sets `is_paused = False`. Next iteration resumes normal operation.
- **`set_interval(seconds: int)`** — Changes sleep duration. Validated: min 10s, max 600s.

### Queries

- **`get_terrace_status() -> TerraceStatus`** — Returns full current state: last photo path, last analysis, last check timestamp, paused flag, interval, cycle count.

### Loop Logic

```
1. Check if paused → if yes, sleep(interval), continue
2. capture_photo(photos_dir) → photo_path
3. analyze_scene(photo_path) → analysis
4. Update workflow state (last_photo_path, last_analysis, last_checked_at)
5. For each recommended_action in analysis:
   - PLAY_SOUND → execute play_sound activity
   - NOTIFY → execute notify_owner activity
   - WATER_PLANTS → execute notify_owner activity (simulated)
   - NONE → skip
6. log_event (always, regardless of actions taken)
7. Increment cycle_count
8. If cycle_count >= threshold → continue-as-new with current state
9. sleep(interval)
```

### Error Handling

- If `analyze_scene` fails after retries: cycle is skipped and logged. No actuators fire. Workflow continues.
- If an actuator activity fails: logged but doesn't block other actuators or the next cycle.
- The workflow never fails permanently — individual cycle failures are isolated.

## Decision Logic

The workflow maps LLM-recommended actions to activity calls. The LLM suggests, the workflow decides. This keeps the workflow deterministic and testable.

Action mapping:
- `PLAY_SOUND` → `play_sound("bird_scare")` — for bird/animal detection
- `NOTIFY` → `notify_owner(title, reason)` — for rain exposure, general alerts
- `WATER_PLANTS` → `notify_owner("Plants Need Water", reason)` — simulated, sends notification
- `NONE` → no activity dispatched

## Project Structure

```
test_project/
├── pyproject.toml
├── main.py                 # CLI: worker, start, pause, resume, status, interval
├── workflows/
│   ├── __init__.py
│   └── terrace_monitor.py
├── activities/
│   ├── __init__.py
│   ├── camera.py
│   ├── analyzer.py
│   ├── sound.py
│   ├── notifier.py
│   └── logger.py
├── models/
│   ├── __init__.py
│   └── types.py
├── photos/                 # test images (user-provided)
├── sounds/                 # audio files for actuators
│   └── bird_scare.wav
└── logs/                   # event log output
```

## Dependencies

- `temporalio>=1.18.2` (already present)
- `anthropic` (Claude vision API)

No other dependencies. `afplay` and `osascript` are built into macOS.

## CLI Interface (main.py)

- `python main.py worker` — starts the Temporal worker
- `python main.py start` — starts the monitoring workflow (default config)
- `python main.py start --interval 60 --photos-dir ./my-photos` — starts with custom config
- `python main.py pause` — sends pause signal
- `python main.py resume` — sends resume signal
- `python main.py status` — queries and prints current terrace status
- `python main.py interval 60` — changes monitoring interval to 60s

Uses `argparse` for CLI parsing.

## Infrastructure

- Temporal dev server running locally (`temporal server start-dev`)
- Task queue: `terrace-monitor`
- Temporal server address: `localhost:7233`
- `ANTHROPIC_API_KEY` environment variable must be set

## Demo Scenario

1. Drop 3-4 test images into `photos/` (bird on railing, dry potted plants, rain with cushions outside, clean empty terrace)
2. Start Temporal dev server
3. Start worker in one terminal
4. Start workflow in another terminal
5. Watch: system cycles through images, plays sound when it detects a bird, pops up notification for rain/plants, logs "all clear" for the clean terrace
6. Demo signals: pause, resume, change interval, query status
