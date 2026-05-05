import argparse
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

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
        activity_executor=ThreadPoolExecutor(max_workers=4),
        workflow_runner=SandboxedWorkflowRunner(
            restrictions=SandboxRestrictions.default.with_passthrough_modules()
        ),
    )
    print(f"Worker started on task queue '{TASK_QUEUE}'")
    await worker.run()


async def start_workflow(photos_dir: str, interval: int, num_cycles: int):
    client = await Client.connect("localhost:7233", plugins=[PydanticAIPlugin()])
    config = MonitorConfig(photos_dir=photos_dir, interval_seconds=interval, num_cycles=num_cycles)
    handle = await client.start_workflow(
        TerraceMonitorWorkflow.run,
        config,
        id=WORKFLOW_ID,
        task_queue=TASK_QUEUE,
    )
    print(f"Workflow started: {handle.id}")
    print(f"  Photos dir: {photos_dir}")
    print(f"  Interval: {interval}s")
    print(f"  Cycles: {'infinite' if num_cycles == 0 else num_cycles}")


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
    start_parser.add_argument("--num-cycles", type=int, default=0, help="Stop after N cycles (0 = infinite)")

    subparsers.add_parser("pause", help="Pause monitoring")
    subparsers.add_parser("resume", help="Resume monitoring")
    subparsers.add_parser("status", help="Query current terrace status")

    interval_parser = subparsers.add_parser("interval", help="Change monitoring interval")
    interval_parser.add_argument("seconds", type=int, help="New interval in seconds")

    args = parser.parse_args()

    if args.command == "worker":
        asyncio.run(run_worker())
    elif args.command == "start":
        asyncio.run(start_workflow(args.photos_dir, args.interval, args.num_cycles))
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
