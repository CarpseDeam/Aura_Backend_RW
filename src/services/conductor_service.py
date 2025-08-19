# src/services/conductor_service.py
import logging
import asyncio
import json
from typing import Dict, Optional, List, Any, TYPE_CHECKING

from src.core.websockets import websocket_manager
from src.event_bus import EventBus
from src.prompts.coder import CODER_PROMPT

if TYPE_CHECKING:
    from src.core.managers import ServiceManager


logger = logging.getLogger(__name__)


class ConductorService:
    """
    Orchestrates the execution of a mission by looping through tasks, handling
    failures with a two-tiered correction system (retry and re-plan), and
    determining the tool call for each step.
    """
    MAX_RETRIES_PER_TASK = 1

    def __init__(
            self,
            event_bus: EventBus,
            service_manager: "ServiceManager"
    ):
        self.event_bus = event_bus
        # --- REFACTOR: Get dependencies from the manager ---
        self.service_manager = service_manager
        self.mission_log_service = service_manager.mission_log_service
        self.tool_runner_service = service_manager.tool_runner_service
        self.development_team_service = service_manager.development_team_service
        self.foundry_manager = service_manager.foundry_manager
        self.llm_client = service_manager.llm_client
        self.db = service_manager.db
        # --- End Refactor ---

        self.is_mission_active = False
        self.original_user_goal = ""
        logger.info("ConductorService initialized.")


    async def _get_tool_call_for_task(self, user_id: str, task: Dict[str, Any], last_error: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        The "brain" of the Conductor. It uses the LLM to translate a task
        into a single, executable tool call.
        """
        current_task_description = task['description']
        log_tasks = self.mission_log_service.get_tasks()
        mission_log_history = "\n".join(
            [f"- ID {t['id']} ({'Done' if t['done'] else 'Pending'}): {t['description']}" for t in log_tasks])
        if not mission_log_history:
            mission_log_history = "This is the first task."
        if last_error:
            current_task_description += f"\n\n**PREVIOUS ATTEMPT FAILED!** Last error: `{last_error}`. You MUST try a different approach."

        vector_context = "Vector context (RAG) is currently disabled."
        file_structure = "\n".join(sorted(self.tool_runner_service.project_manager.get_project_files().keys())) or "The project is currently empty."
        available_tools = self.foundry_manager.get_llm_tool_definitions()

        prompt = CODER_PROMPT.format(
            current_task=current_task_description,
            mission_log=mission_log_history,
            file_structure=file_structure,
            relevant_code_snippets=vector_context
        )
        messages = [{"role": "user", "content": prompt}]

        # This call now goes through the DevTeam service, but only as a passthrough to the LLM
        response_str = await self.development_team_service._make_llm_call(int(user_id), "coder", messages, is_json=True, tools=available_tools)

        if response_str.startswith("Error:"):
            self.log("error", f"Conductor's LLM call failed. Details: {response_str}")
            return None

        try:
            tool_call = self.development_team_service._parse_json_response(response_str)
            if "tool_name" not in tool_call or "arguments" not in tool_call:
                raise ValueError("Response must be JSON with 'tool_name' and 'arguments'.")

            # If the chosen tool is `write_file`, intercept to generate the code first.
            if tool_call.get("tool_name") == "write_file":
                args = tool_call.get("arguments", {})
                if not args.get("content") and args.get("task_description"):
                    # --- THE FIX: Pass the current_task_id to the code generator ---
                    generated_code = await self.development_team_service._generate_code_for_task(
                        user_id,
                        args.get("path"),
                        args.get("task_description"),
                        self.original_user_goal,
                        task['id']  # Pass the ID of the current task
                    )
                    if generated_code.startswith("Error:"):
                        self.log("error", f"Code generation failed for write_file. Details: {generated_code}")
                        return None
                    tool_call["arguments"]["content"] = generated_code
                    tool_call["arguments"].pop("task_description", None)

            return tool_call
        except (ValueError, json.JSONDecodeError) as e:
            self.log("error", f"Conductor failed to parse LLM tool call response. Raw: {response_str}. Error: {e}")
            return None

    async def execute_mission_in_background(self, user_id: str):
        self.is_mission_active = True
        self.original_user_goal = self.mission_log_service.get_initial_goal()
        try:
            await websocket_manager.broadcast_to_user({"type": "agent_status", "status": "thinking"}, user_id)
            await self.execute_mission(user_id)
        finally:
            self.is_mission_active = False
            await websocket_manager.broadcast_to_user({"type": "agent_status", "status": "idle"}, user_id)
            self.log("info", f"Conductor finished mission for user {user_id}.")

    async def execute_mission(self, user_id: str):
        """The main agentic loop, now with its own intelligence."""
        try:
            await self._post_chat_message(user_id, "Conductor", "Mission dispatched. Beginning autonomous execution.")
            while True:
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
                    self.log("info", f"Executing task {current_task['id']}: {current_task['description']}")
                    tool_call = await self._get_tool_call_for_task(user_id, current_task, current_task.get('last_error'))

                    if not tool_call:
                        error_msg = f"Could not determine a tool call for task: '{current_task['description']}'"
                        current_task['last_error'] = error_msg
                        retry_count += 1
                        continue

                    result = await self.tool_runner_service.run_tool_by_dict(tool_call, user_id=user_id)
                    result_is_error, error_message = self._is_result_an_error(result)

                    if not result_is_error:
                        await self.mission_log_service.mark_task_as_done(user_id, current_task['id'])
                        await self._post_chat_message(user_id, "Conductor", f"Task completed: {current_task['description']}")
                        task_succeeded = True
                        break
                    else:
                        current_task['last_error'] = error_message
                        retry_count += 1
                        self.log("warning", f"Task {current_task['id']} failed. Error: {error_message}.")
                        await self._post_chat_message(user_id, "Conductor", f"Task failed, retrying. Error: {error_message}", is_error=True)

                if not task_succeeded:
                    self.log("error", f"Task {current_task['id']} failed after retries. Re-planning.")
                    await self._post_chat_message(user_id, "Aura", "I'm stuck. Rethinking my approach.", is_error=True)
                    await self._execute_strategic_replan(user_id, current_task)
                else:
                    await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Critical error during mission for user {user_id}: {e}", exc_info=True)
            await self._post_chat_message(user_id, "Aura", f"A critical error stopped the mission: {e}", is_error=True)
            await websocket_manager.broadcast_to_user({"type": "mission_failure", "content": str(e)}, user_id)

    def _is_result_an_error(self, result: any) -> (bool, Optional[str]):
        if result is None:
            return True, "Tool returned an empty result, which indicates a potential failure."
        if isinstance(result, str) and (result.strip().lower().startswith("error") or "failed" in result.strip().lower()):
            return True, result
        if isinstance(result, dict) and result.get('status', 'success').lower() in ["failure", "error"]:
            return True, result.get('summary') or result.get('full_output') or "Tool indicated failure without a detailed message."
        return False, None

    async def _execute_strategic_replan(self, user_id: str, failed_task: Dict):
        await self.development_team_service.run_strategic_replan(user_id, self.original_user_goal, failed_task, self.mission_log_service.get_tasks())

    async def _handle_mission_completion(self, user_id: str):
        self.log("success", f"Mission Accomplished for user {user_id}!")
        summary = await self.development_team_service.generate_mission_summary(user_id, self.mission_log_service.get_tasks())
        await self._post_chat_message(user_id, "Aura", summary)
        await websocket_manager.broadcast_to_user({"type": "mission_success"}, user_id)

    async def _post_chat_message(self, user_id: str, sender: str, message: str, is_error: bool = False):
        if message and message.strip():
            msg_data = {"type": "aura_response" if sender.lower() == 'aura' else "system_log", "content": message}
            if is_error:
                msg_data["type"] = "system_log"
            await websocket_manager.broadcast_to_user(msg_data, user_id)

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "ConductorService", level, message)