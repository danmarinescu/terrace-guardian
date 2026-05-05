# Terrace Automation System — Design Spec

## Overview

An outdoor terrace monitoring and automation system built on Temporal workflows with Pydantic AI. A camera sensor captures photos at configurable intervals, a Pydantic AI agent (Claude Sonnet 4.6) analyzes the scene and autonomously calls actuator tools (play sound, send notification) — all durably executed via Temporal.

## Architecture

Single long-lived `TerraceMonitorWorkflow` running an infinite loop:

```
capture_photo (activity) → temporal_agent.run(photo) → log_event (activity) → sleep(interval)
```

The Pydantic AI agent handles analysis, decision-making, and actuation in a single step. The agent sees the photo, reasons about it, and calls actuator tools as needed. These tool calls are automatically wrapped as Temporal activities by the `TemporalAgent` integration, making them durable and retryable.

The workflow holds monitoring state and responds to signals (pause/resume/set_interval) and queries (get_terrace_status). After a configurable number of cycles (default 100), it calls `continue-as-new` to keep history bounded, carrying over current state.

Workflow ID is fixed (`terrace-monitor`) to ensure only one instance runs at a time.

## Pydantic AI Integration

### TemporalAgent Setup

```python
from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import TemporalAgent, PydanticAIPlugin

agent = Agent(
    "anthropic:claude-sonnet-4-6",
    instructions="You are a terrace monitoring assistant. You analyze photos of an outdoor terrace and take appropriate actions using the tools available to you.",
    name="terrace_monitor",
)

# Register actuator tools on the agent (see Tools section)

temporal_agent = TemporalAgent(agent)
```

### How It Works

1. `temporal_agent.run(prompt)` is called from within the workflow
2. Pydantic AI sends the photo to Claude Sonnet 4.6 for analysis
3. The LLM reasons about what it sees and decides which tools to call
4. Each tool call (play_sound, notify_owner) is automatically executed as a Temporal activity
5. The agent returns a final text summary of what it found and did

This collapses the previous analyze → decide → actuate pipeline into a single agent invocation.

## Data Models

### CapturedPhoto

Returned by the `capture_photo` activity. Contains everything the workflow needs so it never reads the filesystem directly.

```python
@dataclass
class CapturedPhoto:
    path: str              # file path for logging/status
    data: bytes            # raw image bytes (must be < 2MB)
    media_type: str        # e.g. "image/jpeg"
```

### TerraceStatus

Returned by the `get_terrace_status` query.

```python
@dataclass
class TerraceStatus:
    last_photo_path: str | None
    last_analysis: str | None  # agent's text summary
    last_checked_at: str | None  # ISO timestamp
    is_paused: bool
    interval_seconds: int
    cycle_count: int
```

### MonitorConfig

Workflow input.

```python
@dataclass
class MonitorConfig:
    photos_dir: str = "photos"
    interval_seconds: int = 30
    continue_as_new_threshold: int = 100
```

## Agent Tools (Actuators)

Registered on the Pydantic AI agent. Each tool call becomes a Temporal activity automatically.

### play_sound(sound_type: str) -> str

Plays an audio file using macOS `afplay` command. The agent calls this when it detects birds or animals that should be scared away.

- `sound_type`: e.g., `"bird_scare"` — maps to a file in `sounds/` directory
- Falls back to system sound (`/System/Library/Sounds/Funk.aiff`) if file not found
- Returns a confirmation message

### notify_owner(title: str, message: str) -> str

Sends a macOS system notification via `osascript`. The agent calls this for conditions requiring human attention: rain with exposed items, plants needing water, or other alerts.

- `title`: notification title (e.g., "Rain Alert")
- `message`: notification body (e.g., "Cushions are getting wet on the terrace")
- Returns a confirmation message

## Regular Activities (Non-Agent)

These are standard Temporal activities, not agent tools, because they run outside the agent's scope.

### capture_photo(photos_dir: str) -> CapturedPhoto

Reads the next image file from the `photos/` directory, cycling alphabetically (round-robin). Returns a `CapturedPhoto` containing the file path, raw image bytes, and media type. Photos must be under 2MB to fit within Temporal's payload limit. Tracks position via a simple counter that wraps around.

- Retry: 1 attempt
- Timeout: 10s

### log_event(summary: str, photo_path: str, actions_taken: list[str]) -> None

Writes a structured JSON log entry to console (stdout) and appends to `logs/events.jsonl`. Logs every cycle including "no action needed" so there's a full history.

- Retry: none
- Timeout: 5s

## Workflow: TerraceMonitorWorkflow

### Signals

- **`pause`** — Sets `is_paused = True`. Loop continues but skips the agent run.
- **`resume`** — Sets `is_paused = False`. Next iteration resumes normal operation.
- **`set_interval(seconds: int)`** — Changes sleep duration. Validated: min 10s, max 600s.

### Queries

- **`get_terrace_status() -> TerraceStatus`** — Returns full current state: last photo path, last analysis summary, last check timestamp, paused flag, interval, cycle count.

### Loop Logic

```
1. Check if paused → if yes, sleep(interval), continue
2. capture_photo(photos_dir) → CapturedPhoto (path, bytes, media_type)
3. temporal_agent.run(prompt + BinaryContent from captured photo) → result
4. Update workflow state (last_photo_path, last_analysis = result.output, last_checked_at)
5. log_event(result.output, photo_path, actions_taken)
6. Increment cycle_count
7. If cycle_count >= threshold → continue-as-new with current state
8. sleep(interval)
```

### Agent Prompt

The agent receives a prompt each cycle containing:
- The photo (as base64 image content)
- Instructions to analyze the terrace scene
- Context: "Look for birds/animals, check plant health, assess weather conditions and rain risk to exposed items. Use your tools to take action if needed. If nothing requires attention, just describe what you see."

### Error Handling

- If the agent run fails after retries: cycle is skipped and logged. Workflow continues.
- Individual tool failures within the agent are handled by Temporal's activity retry mechanism.
- The workflow never fails permanently — individual cycle failures are isolated.

## Project Structure

```
test_project/
├── pyproject.toml
├── main.py                 # CLI: worker, start, pause, resume, status, interval
├── workflows/
│   ├── __init__.py
│   └── terrace_monitor.py  # TerraceMonitorWorkflow
├── activities/
│   ├── __init__.py
│   ├── camera.py           # capture_photo
│   └── logger.py           # log_event
├── agent/
│   ├── __init__.py
│   ├── terrace_agent.py    # Agent definition + TemporalAgent wrapping
│   └── tools.py            # play_sound, notify_owner tool definitions
├── models/
│   ├── __init__.py
│   └── types.py            # TerraceStatus, MonitorConfig
├── photos/                 # test images (user-provided)
├── sounds/                 # audio files for actuators
│   └── bird_scare.wav
└── logs/                   # event log output
```

## Dependencies

- `temporalio>=1.18.2` (already present)
- `pydantic-ai[anthropic]` (Pydantic AI with Anthropic model support)

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
5. Watch: system cycles through images, agent analyzes each scene — plays a sound when it detects a bird, pops up a macOS notification for rain/plants, logs "all clear" for the clean terrace
6. Demo signals: pause, resume, change interval, query status to see latest analysis
