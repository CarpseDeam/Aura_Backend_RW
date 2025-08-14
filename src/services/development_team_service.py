# src/services/development_team_service.py
from __future__ import annotations
import json
import re
from typing import TYPE_CHECKING, Dict, List, Optional, Any
import asyncio

from src.core.websockets import websocket_manager
from src.event_bus import EventBus
from src.prompts.creative import AURA_PLANNER_PROMPT, AURA_REPLANNER_PROMPT, AURA_MISSION_SUMMARY_PROMPT
from src.prompts.coder import CODER_PROMPT
from src.prompts.master_rules import JSON_OUTPUT_RULE, SENIOR_ARCHITECT_HEURISTIC_RULE
from src.prompts.companion import COMPANION_PROMPT

if TYPE_CHECKING:
    from src.core.managers import ServiceManager


class DevelopmentTeamService:
    """
    Orchestrates the main AI workflows by delegating to specialized services
    and handling different planning and execution modes.
    """

    def __init__(self, event_bus: EventBus, service_manager: "ServiceManager"):
        self.event_bus = event_bus
        self.service_manager = service_manager
        self.llm_client = service_manager.get_llm_client()
        self.project_manager = service_manager.project_manager
        self.mission_log_service = service_manager.mission_log_service
        self.vector_context_service = service_manager.vector_context_service
        self.foundry_manager = service_manager.get_foundry_manager()

    async def run_companion_chat(self, user_id: str, user_prompt: str, conversation_history: list) -> str:
        """
        Uses a conversational prompt to chat with the user as a friendly companion.
        """
        self.log("info", f"Companion chat initiated for user {user_id}")

        prompt = COMPANION_PROMPT.format(
            conversation_history="\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history]),
            user_prompt=user_prompt
        )

        provider, model = self.llm_client.get_model_for_role("chat")
        if not provider or not model:
            return "Error: No 'chat' model is configured."

        response_stream = self.llm_client.stream_chat(provider, model, prompt, "chat")
        full_response = "".join([chunk async for chunk in response_stream])

        return full_response.strip()

    async def _post_chat_message(self, user_id: str, sender: str, message: str, is_error: bool = False):
        if message and message.strip():
            msg_data = {
                "type": "aura_response" if sender.lower() == 'aura' else "system_log",
                "content": message
            }
            if is_error:
                msg_data["type"] = "system_log"
            await websocket_manager.broadcast_to_user(msg_data, user_id)

    def _parse_json_response(self, response: str) -> dict:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in the response. Raw response: {response}")
        return json.loads(match.group(0))

    async def run_aura_planner_workflow(self, user_id: str, user_idea: str, conversation_history: list):
        self.log("info", f"Aura planner workflow initiated for user {user_id}: '{user_idea[:50]}...'")
        provider, model = self.llm_client.get_model_for_role("planner")
        if not provider or not model:
            await self.handle_error(user_id, "Aura", "No 'planner' model configured.")
            return

        prompt = AURA_PLANNER_PROMPT.format(
            SENIOR_ARCHITECT_HEURISTIC_RULE=SENIOR_ARCHITECT_HEURISTIC_RULE.strip(),
            conversation_history="\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history]),
            user_idea=user_idea
        )
        response_str = "".join(
            [chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "planner")])

        try:
            plan_data = self._parse_json_response(response_str)
            plan_steps = plan_data.get("plan", [])
            if not plan_steps:
                raise ValueError("Aura's plan was empty or malformed.")

            await self.mission_log_service.set_initial_plan(user_id, plan_steps, user_idea)
            await self._post_chat_message(user_id, "Aura",
                                          "I've created a plan. Review it in the 'Agent TODO' list and click 'Dispatch Aura' to begin.")
        except (ValueError, json.JSONDecodeError) as e:
            await self.handle_error(user_id, "Aura", f"Failed to create a valid plan: {e}.")
            self.log("error", f"Aura planner failure for user {user_id}. Raw response: {response_str}")

    async def run_coding_task(self, task: Dict[str, any], last_error: Optional[str] = None) -> Optional[Dict[str, str]]:
        if task.get("tool_call"):
            self.log("info", f"Using pre-defined tool call for task: {task['description']}")
            return task["tool_call"]
        current_task_description = task['description']
        log_tasks = self.mission_log_service.get_tasks()
        mission_log_history = "\n".join(
            [f"- ID {t['id']} ({'Done' if t['done'] else 'Pending'}): {t['description']}" for t in log_tasks])
        if not mission_log_history:
            mission_log_history = "This is the first task."
        if last_error:
            current_task_description += f"\n\n**PREVIOUS ATTEMPT FAILED!** Last error: `{last_error}`. You MUST try a different approach."
        vector_context = "No existing code snippets were found."
        file_structure = "\n".join(
            sorted(self.project_manager.get_project_files().keys())) or "The project is currently empty."
        available_tools = json.dumps(self.foundry_manager.get_llm_tool_definitions(), indent=2)
        prompt = CODER_PROMPT.format(
            current_task=current_task_description, mission_log=mission_log_history,
            available_tools=available_tools, file_structure=file_structure,
            relevant_code_snippets=vector_context, JSON_OUTPUT_RULE=JSON_OUTPUT_RULE.strip()
        )
        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.log("error", "No 'coder' model configured.")
            return None
        response_str = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "coder")])
        try:
            tool_call = self._parse_json_response(response_str)
            if "tool_name" not in tool_call or "arguments" not in tool_call:
                raise ValueError("Response must be JSON with 'tool_name' and 'arguments'.")
            return tool_call
        except (ValueError, json.JSONDecodeError) as e:
            self.log("error", f"Coder generation failure. Raw response: {response_str}. Error: {e}")
            return None

    async def run_strategic_replan(self, user_id: str, original_goal: str, failed_task: Dict, mission_log: List[Dict]):
        self.log("info", "Strategic re-plan initiated.")
        await self._post_chat_message(user_id, "Aura", "Hitting a roadblock. Rethinking the plan...")
        mission_log_str = "\n".join(
            [f"- ID {t['id']} ({'Done' if t['done'] else 'Pending'}): {t['description']}" for t in mission_log])
        failed_task_str = f"ID {failed_task['id']}: {failed_task['description']}"
        error_message = failed_task.get('last_error', 'No specific error message was recorded.')
        prompt = AURA_REPLANNER_PROMPT.format(
            user_goal=original_goal, mission_log=mission_log_str,
            failed_task=failed_task_str, error_message=error_message
        )
        provider, model = self.llm_client.get_model_for_role("planner")
        if not provider or not model:
            await self.handle_error(user_id, "Aura", "No 'planner' model available for re-planning.")
            return
        response_str = "".join(
            [chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "planner")])
        try:
            new_plan_data = self._parse_json_response(response_str)
            new_plan_steps = new_plan_data.get("plan", [])
            if not new_plan_steps:
                raise ValueError("Re-planner returned an empty or malformed plan.")
            await self.mission_log_service.replace_tasks_from_id(user_id, failed_task['id'], new_plan_steps)
            self.log("success", f"Successfully replaced failed task for user {user_id} with a new plan.")
            await self._post_chat_message(user_id, "Aura", "I have a new plan. Resuming execution.")
        except (ValueError, json.JSONDecodeError) as e:
            await self.handle_error(user_id, "Aura", f"I failed to create a valid recovery plan: {e}")
            self.log("error", f"Aura re-planner failure for user {user_id}. Raw response: {response_str}")

    async def generate_mission_summary(self, user_id: str, completed_tasks: List[Dict]) -> str:
        task_descriptions = "\n".join([f"- {task['description']}" for task in completed_tasks if task['done']])
        if not task_descriptions:
            return "Mission accomplished!"
        prompt = AURA_MISSION_SUMMARY_PROMPT.format(completed_tasks=task_descriptions)
        provider, model = self.llm_client.get_model_for_role("chat")
        if not provider or not model:
            self.log("error", "No 'chat' model available for summary generation.")
            return "Mission accomplished!"
        summary = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "chat")])
        return summary.strip() if summary.strip() else "Mission accomplished!"

    async def handle_error(self, user_id: str, agent: str, error_msg: str):
        self.log("error", f"{agent} failed for user {user_id}: {error_msg}")
        await self._post_chat_message(user_id, "Aura", error_msg, is_error=True)

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "DevTeamService", level, message)