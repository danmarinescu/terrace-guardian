from datetime import timedelta
from pathlib import Path

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from pydantic_ai import BinaryContent, ToolCallPart
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
                BinaryContent(data=Path(photo.path).read_bytes(), media_type=photo.media_type),
            ]
        )

        self._last_analysis = result.output
        now = workflow.now().isoformat()
        self._last_checked_at = now

        # Extract tool calls from all messages: iterate over ModelResponse parts
        actions_taken = [
            f"{part.tool_name}({part.args})"
            for message in result.all_messages()
            for part in getattr(message, "parts", [])
            if isinstance(part, ToolCallPart)
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
