# src/services/conductor_service.py
import logging
import asyncio
from typing import Dict, Optional

from src.core.websockets import websocket_manager
from src.event_bus import EventBus
from .mission_log_service import MissionLogService
from .tool_runner_service import ToolRunnerService
from .development_team_service import DevelopmentTeamService

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
        self.is_mission_active = False # This should be managed per-user
        self.original_user_goal = ""
        logger.info("ConductorService initialized.")

    async def execute_mission_in_background(self, user_id: str):
        # We might need a more robust way to prevent concurrent missions for the same user
        # For now, this acts as a simple entry point.
        self.is_mission_active = True
        self.original_user_goal = self.mission_log_service.get_initial_goal()
        await self.execute_mission(user_id)

    async def execute_mission(self, user_id: str):
        """
        The main agentic loop for a specific user.
        """
        try:
            await self._post_chat_message(user_id, "Conductor", "Mission dispatched. Beginning autonomous execution.")

            while True:
                # In a real multi-user system, you'd check a user-specific "is_active" flag
                if not self.is_mission_active:
                    self.log("info", f"Mission for user {user_id} was stopped.")
                    break

                pending_tasks = self.mission_log_service.get_tasks(done=False)
                if not pending_tasks:
                    await self._handle_mission_completion(user_id)
                    break

                current_task = pending_tasks[0]
                retry_count = 0
                task_succeeded = False

                while retry_count <= self.MAX_RETRIES_PER_TASK:
                    self.log("info", f"Executing task {current_task['id']} for user {user_id}: {current_task['description']}")
                    tool_call = await self.development_team_service.run_coding_task(
                        task=current_task,
                        last_error=current_task.get('last_error')
                    )

                    if not tool_call:
                        error_msg = f"Could not determine a tool call for task: '{current_task['description']}'"
                        current_task['last_error'] = error_msg
                        retry_count += 1
                        continue

                    result = await self.tool_runner_service.run_tool_by_dict(tool_call)
                    result_is_error, error_message = self._is_result_an_error(result)

                    if not result_is_error:
                        await self.mission_log_service.mark_task_as_done(user_id, current_task['id'])
                        await self._post_chat_message(user_id, "Conductor", f"Task completed: {current_task['description']}")
                        task_succeeded = True
                        break
                    else:
                        current_task['last_error'] = error_message
                        retry_count += 1
                        self.log("warning", f"Task {current_task['id']} failed for user {user_id}. Error: {error_message}.")
                        await self._post_chat_message(user_id, "Conductor", f"Task failed, retrying. Error: {error_message}", is_error=True)

                if not task_succeeded:
                    self.log("error", f"Task {current_task['id']} failed for user {user_id} after retries. Re-planning.")
                    await self._post_chat_message(user_id, "Aura", "I'm stuck. Rethinking my approach.", is_error=True)
                    await self._execute_strategic_replan(user_id, current_task)
                else:
                    await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Critical error during mission for user {user_id}: {e}", exc_info=True)
            await self._post_chat_message(user_id, "Aura", f"A critical error stopped the mission: {e}", is_error=True)
        finally:
            self.is_mission_active = False # Reset user-specific flag
            self.log("info", f"Conductor finished cycle for user {user_id}.")

    def _is_result_an_error(self, result: any) -> (bool, Optional[str]):
        """Determines if a tool result constitutes an error."""
        if isinstance(result, str) and result.strip().lower().startswith("error"):
            return True, result
        if isinstance(result, dict) and result.get('status', 'success').lower() in ["failure", "error"]:
            return True, result.get('summary') or result.get('full_output') or "Unknown error from tool."
        return False, None

    async def _execute_strategic_replan(self, user_id: str, failed_task: Dict):
        """Triggers the Development Team to create a new plan to overcome a persistent failure."""
        await self.development_team_service.run_strategic_replan(
            user_id=user_id,
            original_goal=self.original_user_goal,
            failed_task=failed_task,
            mission_log=self.mission_log_service.get_tasks()
        )

    async def _handle_mission_completion(self, user_id: str):
        """Generates and posts the final summary when all tasks are done."""
        self.log("success", f"Mission Accomplished for user {user_id}!")
        summary = await self.development_team_service.generate_mission_summary(user_id, self.mission_log_service.get_tasks())
        await self._post_chat_message(user_id, "Aura", summary)
        await websocket_manager.broadcast_to_user({"type": "mission_success"}, user_id)


    async def _post_chat_message(self, user_id: str, sender: str, message: str, is_error: bool = False):
        if message and message.strip():
            msg_data = {
                "type": "aura_response" if sender.lower() == 'aura' else "system_log",
                "content": message
            }
            if is_error:
                msg_data["type"] = "system_log"
            await websocket_manager.broadcast_to_user(msg_data, user_id)

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "ConductorService", level, message)