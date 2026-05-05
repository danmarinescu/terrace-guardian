#!/usr/bin/env bash
set -euo pipefail

PHOTOS_DIR="photos"
INTERVAL=15
NUM_CYCLES=5

PIDS=()

cleanup() {
    echo ""
    echo "Shutting down..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

# --- Check ANTHROPIC_API_KEY ---
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "Error: ANTHROPIC_API_KEY is not set."
    echo "  export ANTHROPIC_API_KEY=\"sk-ant-...\""
    exit 1
fi

# --- Install uv if missing ---
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# --- Install dependencies ---
echo "Installing dependencies..."
uv sync --quiet

# --- Install Temporal CLI if missing ---
if ! command -v temporal &>/dev/null; then
    echo "Installing Temporal CLI..."
    brew install temporal 2>/dev/null || {
        echo "Error: Could not install Temporal CLI. Install it manually:"
        echo "  brew install temporal"
        echo "  or: https://docs.temporal.io/cli#install"
        exit 1
    }
fi

# --- Start Temporal dev server ---
if curl -s http://localhost:8233 >/dev/null 2>&1; then
    echo "Temporal server already running on :7233"
else
    echo "Starting Temporal dev server..."
    temporal server start-dev --log-level error &
    PIDS+=($!)

    echo -n "Waiting for Temporal server"
    for i in $(seq 1 30); do
        if curl -s http://localhost:8233 >/dev/null 2>&1; then
            echo " ready."
            break
        fi
        echo -n "."
        sleep 1
        if [ "$i" -eq 30 ]; then
            echo " timed out."
            echo "Error: Temporal server did not start within 30 seconds."
            exit 1
        fi
    done
fi

# --- Start worker ---
echo "Starting worker..."
uv run python main.py worker &
PIDS+=($!)
sleep 2

# --- Start monitoring workflow ---
echo ""
echo "=== Terrace Guardian ==="
echo "  Photos: $PHOTOS_DIR"
echo "  Interval: ${INTERVAL}s"
echo "  Cycles: $NUM_CYCLES"
echo ""

uv run python main.py start --photos-dir "$PHOTOS_DIR" --interval "$INTERVAL" --num-cycles "$NUM_CYCLES"

# --- Tail the event log ---
echo ""
echo "Monitoring started. Watching event log (Ctrl+C to stop)..."
echo ""

touch logs/events.jsonl
tail -f logs/events.jsonl | while IFS= read -r line; do
    echo "$line" | python3 -c "
import json, sys
e = json.loads(sys.stdin.read())
print(f\"  [{e['timestamp'][:19]}] {e['photo_path']}\")
print(f\"    Summary: {e['summary'][:120]}\")
if e.get('actions_taken'):
    print(f\"    Actions: {', '.join(e['actions_taken'])}\")
print()
" 2>/dev/null || echo "$line"
done
