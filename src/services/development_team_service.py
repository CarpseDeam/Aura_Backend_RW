# src/services/development_team_service.py
from __future__ import annotations
import json
import re
import os
import aiohttp
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from src.core.websockets import websocket_manager
from src.event_bus import EventBus
from src.prompts.creative import AURA_PLANNER_PROMPT, AURA_REPLANNER_PROMPT, AURA_MISSION_SUMMARY_PROMPT
from src.prompts.coder import CODER_PROMPT
from src.prompts.master_rules import JSON_OUTPUT_RULE, SENIOR_ARCHITECT_HEURISTIC_RULE
from src.prompts.companion import COMPANION_PROMPT
from src.db import crud

if TYPE_CHECKING:
    from src.core.managers import ServiceManager


class DevelopmentTeamService:
    """
    Orchestrates the main AI workflows by delegating to specialized services
    and handling different planning and execution modes.
    This version now calls a dedicated, external LLM microservice.
    """

    def __init__(self, event_bus: EventBus, service_manager: "ServiceManager"):
        self.event_bus = event_bus
        self.service_manager = service_manager
        self.llm_client = service_manager.get_llm_client()
        self.project_manager = service_manager.project_manager
        self.mission_log_service = service_manager.mission_log_service
        self.vector_context_service = service_manager.vector_context_service
        self.foundry_manager = service_manager.get_foundry_manager()
        self.db = service_manager.db
        self.llm_server_url = os.getenv("LLM_SERVER_URL")  # Get the microservice URL from env vars

        assignments_from_db = crud.get_assignments_for_user(self.db, user_id=self.service_manager.user_id)
        self.llm_client.set_assignments({a.role_name: a.model_identifier for a in assignments_from_db})

    async def _make_llm_call(self, user_id: int, role: str, messages: List[Dict[str, Any]],
                             is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Makes a secure, asynchronous HTTP call to the dedicated LLM microservice.
        """
        if not self.llm_server_url:
            return "Error: LLM_SERVER_URL is not configured. The main app cannot contact the AI microservice."

        provider_name, model_name = self.llm_client.get_model_for_role(role)
        if not provider_name or not model_name:
            return f"Error: No model assigned for role '{role}'."

        api_key = crud.get_decrypted_key_for_provider(self.db, user_id, provider_name=provider_name)
        if not api_key:
            return f"Error: No API key configured for provider '{provider_name}'."

        payload = {
            "provider_name": provider_name,
            "model_name": model_name,
            "messages": messages,
            "temperature": self.llm_client.get_role_temperature(role),
            "is_json": is_json,
            "tools": tools,
        }
        headers = {
            "Content-Type": "application/json",
            "X-Provider-API-Key": api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                invoke_url = f"{self.llm_server_url}/invoke"
                async with session.post(invoke_url, json=payload, headers=headers, timeout=300) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("reply", "Error: Invalid response from LLM service.")
                    else:
                        error_detail = await response.text()
                        self.log("error", f"LLM service returned error {response.status}: {error_detail}")
                        return f"Error: The AI microservice failed to process the request. Status: {response.status}. Details: {error_detail}"
        except aiohttp.ClientError as e:
            self.log("error", f"Could not connect to LLM service at {self.llm_server_url}. Error: {e}")
            return f"Error: Could not connect to the AI microservice. Please ensure it is running and the URL is correct."
        except Exception as e:
            self.log("error", f"An unexpected error occurred while calling the LLM service: {e}")
            return f"An unexpected error occurred while calling the AI microservice: {e}"

    async def run_companion_chat(self, user_id: str, user_prompt: str, conversation_history: list) -> str:
        self.log("info", f"Companion chat initiated for user {user_id}")
        prompt = COMPANION_PROMPT.format(
            conversation_history="\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history]),
            user_prompt=user_prompt
        )
        # For companion chat, we create a system prompt and then the user message
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_prompt}
        ]
        # We merge the conversation history for context, but keep it clean
        full_history = conversation_history + messages
        return await self._make_llm_call(int(user_id), "chat", full_history)

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
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                raise ValueError(f"No JSON object found in the response. Raw response: {response}")
            return json.loads(match.group(0))

    async def run_aura_planner_workflow(self, user_id: str, user_idea: str, conversation_history: list):
        self.log("info", f"Aura planner workflow initiated for user {user_id}: '{user_idea[:50]}...'")
        prompt = AURA_PLANNER_PROMPT.format(
            SENIOR_ARCHITECT_HEURISTIC_RULE=SENIOR_ARCHITECT_HEURISTIC_RULE.strip(),
            conversation_history="\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history]),
            user_idea=user_idea
        )
        messages = conversation_history + [{"role": "user", "content": prompt}]

        response_str = await self._make_llm_call(int(user_id), "planner", messages, is_json=True)

        if response_str.startswith("Error:"):
            await self.handle_error(user_id, "Aura", response_str)
            return

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

    async def run_coding_task(self, user_id: str, task: Dict[str, any], last_error: Optional[str] = None) -> Optional[
        Dict[str, str]]:
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

        available_tools = self.foundry_manager.get_llm_tool_definitions()

        prompt = CODER_PROMPT.format(
            current_task=current_task_description, mission_log=mission_log_history,
            available_tools=json.dumps(available_tools, indent=2),
            file_structure=file_structure,
            relevant_code_snippets=vector_context, JSON_OUTPUT_RULE=JSON_OUTPUT_RULE.strip()
        )
        messages = [{"role": "user", "content": prompt}]

        response_str = await self._make_llm_call(int(user_id), "coder", messages, is_json=True, tools=available_tools)

        if response_str.startswith("Error:"):
            self.log("error", f"Coder generation failure. Details: {response_str}")
            return None

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
        messages = [{"role": "user", "content": prompt}]
        response_str = await self._make_llm_call(int(user_id), "planner", messages, is_json=True)

        if response_str.startswith("Error:"):
            await self.handle_error(user_id, "Aura", response_str)
            return

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
        messages = [{"role": "user", "content": prompt}]
        summary = await self._make_llm_call(int(user_id), "chat", messages)
        return summary.strip() if summary.strip() else "Mission accomplished!"

    async def handle_error(self, user_id: str, agent: str, error_msg: str):
        self.log("error", f"{agent} failed for user {user_id}: {error_msg}")
        await self._post_chat_message(user_id, "Aura", error_msg, is_error=True)

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "DevTeamService", level, message)