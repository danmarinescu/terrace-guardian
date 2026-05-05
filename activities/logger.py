import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
def log_event(
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
    logger.info(log_line)

    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(log_line + "\n")
