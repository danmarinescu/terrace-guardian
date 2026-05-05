# Terrace Guardian

An AI-powered outdoor terrace monitoring system built with [Temporal](https://temporal.io) and [Pydantic AI](https://pydantic.dev/docs/ai/).

A camera captures photos of the terrace at regular intervals. Each photo is sent to Claude (Sonnet 4.6) through a Pydantic AI agent. Based on what it sees, the system autonomously takes action:

- **Bird detected** &rarr; plays a scare sound via macOS `afplay`
- **Plants look dry** &rarr; sends a macOS notification to water them
- **Rain + exposed cushions/furniture** &rarr; sends an urgent notification
- **Fire or other hazards** &rarr; sends a safety alert
- **All clear** &rarr; logs the observation, no action needed

The entire pipeline runs as a durable Temporal workflow with pause/resume controls, configurable intervals, and a live status query.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              TerraceMonitorWorkflow                      │
│                                                         │
│  Loop:                                                  │
│    capture_photo ──► Pydantic AI Agent ──► log_event    │
│    (activity)        (Claude vision +      (activity)   │
│                       tool calls)                       │
│                          │                              │
│                    ┌─────┴──────┐                       │
│                    ▼            ▼                        │
│              play_sound   notify_owner                   │
│              (afplay)     (osascript)                    │
│                                                         │
│  Signals: pause | resume | set_interval                 │
│  Query:   get_terrace_status                            │
└─────────────────────────────────────────────────────────┘
```

The Pydantic AI agent's LLM calls and tool invocations are automatically wrapped as Temporal activities, making them durable and retryable.

## Quick start

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
./run.sh
```

That's it. The script installs uv and the Temporal CLI if missing, starts the Temporal dev server, launches the worker, runs the demo (5 photos, 15s apart), and tails the event log. Press Ctrl+C to stop everything.

## Prerequisites

- macOS (for `afplay` sound and `osascript` notifications)
- [Homebrew](https://brew.sh/) (used to install Temporal CLI if not present)
- An [Anthropic API key](https://console.anthropic.com/)

## Manual setup

If you prefer to run things yourself:

```bash
# Install dependencies
uv sync

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Start the Temporal dev server (in a separate terminal)
temporal server start-dev
```

## Running manually

### 1. Start the worker

```bash
uv run python main.py worker
```

### 2. Start the monitoring workflow

```bash
# Run continuously (every 30s)
uv run python main.py start

# Run with custom interval
uv run python main.py start --interval 15

# Run each photo once then stop (good for demos)
uv run python main.py start --interval 15 --num-cycles 5

# Use a different photos directory
uv run python main.py start --photos-dir ./my-photos
```

### 3. Control the workflow

```bash
# Pause monitoring (workflow stays alive but skips cycles)
uv run python main.py pause

# Resume monitoring
uv run python main.py resume

# Change the interval to 60 seconds
uv run python main.py interval 60

# Query current status (returns JSON)
uv run python main.py status
```

## Checking output

### Event log

Every cycle is logged to `logs/events.jsonl` — one JSON line per cycle with timestamp, photo path, analysis summary, and actions taken:

```bash
# Watch the log in real time
tail -f logs/events.jsonl | python -m json.tool

# See just the summaries
cat logs/events.jsonl | python -c "
import json, sys
for line in sys.stdin:
    e = json.loads(line)
    print(f\"{e['timestamp'][:19]}  {e['photo_path']:25s}  actions={e['actions_taken']}\")
"
```

### Workflow status query

```bash
uv run python main.py status
```

Returns JSON with the latest analysis, last photo processed, whether monitoring is paused, current interval, and cycle count.

### Temporal UI

Open http://localhost:8233 in a browser to see the workflow history — activity completions, signals received, timer events, and any errors.

## Test photos

Place images in the `photos/` directory. The system cycles through them alphabetically. The included test photos are:

| Photo | Scenario |
|-------|----------|
| `all_good.jpg` | Clean terrace, sunny day, no issues |
| `bird.jpg` | Pigeon on the coffee table |
| `dry.jpg` | Plants showing drought stress |
| `fire.jpg` | Fire pit with large flames + overcast/wet conditions |
| `rain.jpg` | Heavy rain with exposed cushions and furniture |

## Running tests

```bash
uv run pytest tests/ -v
```

## Project structure

```
├── main.py                  # CLI entry point
├── workflows/
│   └── terrace_monitor.py   # Temporal workflow
├── activities/
│   ├── camera.py            # Photo capture (round-robin from directory)
│   └── logger.py            # JSONL event logging
├── agent/
│   ├── terrace_agent.py     # Pydantic AI agent + TemporalAgent wrapper
│   └── tools.py             # Actuators: play_sound, notify_owner
├── models/
│   └── types.py             # Data types: CapturedPhoto, MonitorConfig, TerraceStatus
├── photos/                  # Test images
├── sounds/                  # Sound files for bird scare (falls back to system sound)
└── logs/                    # Event log output
```
