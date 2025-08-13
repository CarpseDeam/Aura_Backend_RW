# src/services/conductor_service.py
import logging
import asyncio
from typing import Dict, Optional

from src.event_bus import EventBus
from .mission_log_service import MissionLogService
from .tool_runner_service import ToolRunnerService
from .development_team_service import DevelopmentTeamService
from src.events import PostChatMessage, MissionAccomplished

logger = logging.getLogger(__name__)


class ConductorService:
    """
    Orchestrates the execution of a mission by looping through tasks, handling
    failures with a two-tiered correction system (retry and re-plan), and
    delegating the "how-to" for each step to the DevelopmentTeamService.
    """
    MAX_RETRIES_PER_TASK = 1

    def __init__(
            self,
            event_bus: EventBus,
            mission_log_service: MissionLogService,
            tool_runner_service: ToolRunnerService,
            development_team_service: DevelopmentTeamService
    ):
        self.event_bus = event_bus
        self.mission_log_service = mission_log_service
        self.tool_runner_service = tool_runner_service
        self.development_team_service = development_team_service
        self.is_mission_active = False
        self.original_user_goal = ""
        logger.info("ConductorService initialized.")

    def execute_mission_in_background(self, event=None):
        if self.is_mission_active:
            self.log("warning", "Mission is already in progress.")
            return
        self.is_mission_active = True
        if not self.original_user_goal:
            self.original_user_goal = self.mission_log_service.get_initial_goal()

        asyncio.create_task(self.execute_mission())

    async def execute_mission(self):
        """
        The main agentic loop. It processes tasks, retries on failure, and
        triggers a strategic re-plan if a task cannot be completed.
        """
        try:
            self.event_bus.emit("agent_status_changed", "Conductor", "Mission dispatched...", "fa5s.play-circle")
            self._post_chat_message("Conductor", "Mission received. Beginning autonomous execution loop.")

            while True:
                if not self.is_mission_active:
                    self.log("info", "Mission execution was externally stopped.")
                    break

                pending_tasks = self.mission_log_service.get_tasks(done=False)
                if not pending_tasks:
                    await self._handle_mission_completion()
                    break

                current_task = pending_tasks[0]
                retry_count = 0
                task_succeeded = False

                while retry_count <= self.MAX_RETRIES_PER_TASK:
                    self.log("info", f"Executing task {current_task['id']}: {current_task['description']}")
                    tool_call = await self.development_team_service.run_coding_task(
                        task=current_task,
                        last_error=current_task.get('last_error')
                    )

                    if not tool_call:
                        error_msg = f"Could not determine a tool call for task: '{current_task['description']}'"
                        current_task['last_error'] = error_msg
                        retry_count += 1
                        self.log("warning", f"{error_msg}. Retry {retry_count}/{self.MAX_RETRIES_PER_TASK}.")
                        continue

                    result = await self.tool_runner_service.run_tool_by_dict(tool_call)
                    result_is_error, error_message = self._is_result_an_error(result)

                    if not result_is_error:
                        self.mission_log_service.mark_task_as_done(current_task['id'])
                        self._post_chat_message("Conductor", f"Task completed: {current_task['description']}")
                        task_succeeded = True
                        break
                    else:
                        current_task['last_error'] = error_message
                        retry_count += 1
                        self.log("warning", f"Task {current_task['id']} failed. Error: {error_message}. Retry {retry_count}/{self.MAX_RETRIES_PER_TASK}.")
                        self._post_chat_message("Conductor", f"Task failed. I will try again. Error: {error_message}", is_error=True)

                if not task_succeeded:
                    self.log("error", f"Task {current_task['id']} failed after {self.MAX_RETRIES_PER_TASK + 1} attempts. Triggering strategic re-plan.")
                    self._post_chat_message("Aura", "I seem to be stuck. I'm going to rethink my approach.", is_error=True)
                    await self._execute_strategic_replan(current_task)
                    # The loop will continue with the new plan on the next iteration
                else:
                    await asyncio.sleep(0.5) # Small delay between successful tasks

        except Exception as e:
            logger.error(f"A critical error occurred during mission execution: {e}", exc_info=True)
            self.event_bus.emit("agent_status_changed", "Conductor", f"Mission Failed: {e}", "fa5s.exclamation-circle")
            self._post_chat_message("Aura", f"A critical error stopped the mission: {e}", is_error=True)
        finally:
            self.is_mission_active = False
            self.log("info", "Conductor has finished its cycle and is now idle.")

    def _is_result_an_error(self, result: any) -> (bool, Optional[str]):
        """Determines if a tool result constitutes an error."""
        if isinstance(result, str) and result.strip().lower().startswith("error"):
            return True, result
        if isinstance(result, dict) and result.get('status', 'success').lower() in ["failure", "error"]:
            return True, result.get('summary') or result.get('full_output') or "Unknown error from tool."
        return False, None

    async def _execute_strategic_replan(self, failed_task: Dict):
        """Triggers the Development Team to create a new plan to overcome a persistent failure."""
        await self.development_team_service.run_strategic_replan(
            original_goal=self.original_user_goal,
            failed_task=failed_task,
            mission_log=self.mission_log_service.get_tasks()
        )
        self._post_chat_message("Aura", "I have formulated a new plan. Resuming execution.", is_error=False)

    async def _handle_mission_completion(self):
        """Generates and posts the final summary when all tasks are done."""
        self.log("success", "Mission Accomplished! All tasks completed.")
        self.event_bus.emit("agent_status_changed", "Aura", "Mission Accomplished!", "fa5s.rocket")
        self.event_bus.emit("mission_accomplished", MissionAccomplished())

        summary = await self.development_team_service.generate_mission_summary(self.mission_log_service.get_tasks())
        self._post_chat_message("Aura", summary)

    def _post_chat_message(self, sender: str, message: str, is_error: bool = False):
        self.event_bus.emit("post_chat_message", PostChatMessage(sender, message, is_error))

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "ConductorService", level, message)