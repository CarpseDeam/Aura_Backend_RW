# src/services/development_team_service.py
# src/services/development_team_service.py
from __future__ import annotations

import asyncio
import json
import re
import os
import aiohttp
from typing import TYPE_CHECKING, Dict, List, Optional, Any
from sqlalchemy.orm import Session
from pathlib import Path

from src.core.websockets import websocket_manager
from src.event_bus import EventBus
from src.prompts.creative import AURA_PLANNER_PROMPT, AURA_REPLANNER_PROMPT, AURA_MISSION_SUMMARY_PROMPT
from src.prompts.coder import CODER_PROMPT_STREAMING
from src.prompts.master_rules import SENIOR_ARCHITECT_HEURISTIC_RULE, TYPE_HINTING_RULE, DOCSTRING_RULE, \
    CLEAN_CODE_RULE, MAESTRO_CODER_PHILOSOPHY_RULE, RAW_CODE_OUTPUT_RULE
from src.prompts.companion import COMPANION_PROMPT
from src.db import crud

if TYPE_CHECKING:
    from src.core.managers import ServiceManager


class DevelopmentTeamService:
    """
    Acts as a specialized support service for the Conductor.
    Its responsibilities are now focused on planning, code generation, and summarizing.
    """

    def __init__(
            self,
            event_bus: EventBus,
            service_manager: "ServiceManager"
    ):
        self.event_bus = event_bus
        self.service_manager = service_manager
        self.llm_server_url = os.getenv("LLM_SERVER_URL")

    def refresh_llm_assignments(self):
        """
        (RE)Populates the LLM client with the latest model assignments from the DB.
        This is critical for background tasks that use a new DB session.
        """
        user_id = self.service_manager.user_id
        db = self.service_manager.db
        llm_client = self.service_manager.llm_client

        if user_id is not None and db is not None:
            assignments_from_db = crud.get_assignments_for_user(db, user_id=user_id)
            llm_client.set_assignments({a.role_name: a.model_id for a in assignments_from_db})
            llm_client.set_temperatures({a.role_name: a.temperature for a in assignments_from_db})
            print(f"LLM client assignments refreshed for user {user_id}.")

    async def _unified_llm_streamer(self, user_id: int, role: str, messages: List[Dict[str, Any]],
                                    is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None,
                                    stream_to_user_socket_as: Optional[str] = None, file_path: Optional[str] = None) -> str:
        llm_client = self.service_manager.llm_client
        db = self.service_manager.db
        if not self.llm_server_url:
            return "Error: LLM_SERVER_URL is not configured."

        provider_name, model_name = llm_client.get_model_for_role(role)
        api_key = crud.get_decrypted_key_for_provider(db, user_id, provider_name=provider_name)
        if not all([provider_name, model_name, api_key]):
            return f"Error: Missing config for role '{role}' or provider '{provider_name}'. Please set it in Settings."

        payload = {
            "provider_name": provider_name, "model_name": model_name, "messages": messages,
            "temperature": llm_client.get_role_temperature(role), "is_json": is_json, "tools": tools,
        }
        headers = {"Content-Type": "application/json", "X-Provider-API-Key": api_key}
        final_reply = ""

        try:
            async with aiohttp.ClientSession() as session:
                invoke_url = f"{self.llm_server_url}/invoke"
                async with session.post(invoke_url, json=payload, headers=headers, timeout=300) as response:
                    if response.status != 200:
                        error_detail = await response.text()
                        await self._post_chat_message(str(user_id), "Aura",
                                                      f"Error from AI microservice: {error_detail}", is_error=True)
                        return f"Error: LLM service failed with status {response.status}. Details: {error_detail}"

                    while not response.content.at_eof():
                        line = await response.content.readline()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if data.get("type") == "chunk" and stream_to_user_socket_as:
                                await websocket_manager.broadcast_to_user({
                                    "type": stream_to_user_socket_as,
                                    "content": {"filePath": file_path, "chunk": data.get("content", "")}
                                }, str(user_id))
                            else:
                                await websocket_manager.broadcast_to_user(data, str(user_id))

                            if "final_response" in data and "reply" in data["final_response"]:
                                final_reply = data["final_response"]["reply"]
                        except json.JSONDecodeError:
                            if is_json:
                                self.log("warning", f"Could not decode JSON line from stream: {line}")
                            continue
            return final_reply
        except Exception as e:
            error_msg = f"An unexpected error occurred during streaming: {e}"
            self.log("error", f"Error during unified streaming call for user {user_id}: {e}")
            await self._post_chat_message(str(user_id), "Aura", error_msg, is_error=True)
            return error_msg

    def _parse_json_response(self, response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r''''json\s*(\{.*?\})\s*'''', response, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                raise ValueError(f"No JSON object found in the response. Raw response: {response}")
            return json.loads(match.group(0))

    async def run_companion_chat(self, user_id: str, user_prompt: str, conversation_history: list) -> str:
        self.log("info", f"Companion chat initiated for user {user_id}: '{user_prompt[:50]}...'")
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
        prompt = COMPANION_PROMPT.format(conversation_history=history_str, user_prompt=user_prompt)
        messages = [{"role": "user", "content": prompt}]
        self.refresh_llm_assignments()

        response_str = await self._unified_llm_streamer(int(user_id), "chat", messages)

        if response_str.startswith("Error:"):
            await self.handle_error(user_id, "Companion", response_str)
            return "I'm sorry, I seem to be having trouble connecting to my creative core right now."
        return response_str

    async def run_aura_planner_workflow(self, user_id: str, user_idea: str, conversation_history: list):
        self.log("info", f"Aura planner workflow initiated for user {user_id}: '{user_idea[:50]}...'")
        prompt = AURA_PLANNER_PROMPT.format(user_idea=user_idea)
        messages = [{"role": "user", "content": prompt}]
        self.refresh_llm_assignments()

        response_str = await self._unified_llm_streamer(int(user_id), "planner", messages, is_json=True)

        if not response_str or response_str.strip().startswith("Error:"):
            error_content = response_str or "The Architect AI returned an empty or invalid response. This can happen if the model is overloaded or if it responded with a format that could not be understood (e.g., a tool call instead of a JSON plan)."
            await self.handle_error(user_id, "Aura", error_content)
            return

        try:
            plan_data = self._parse_json_response(response_str)
            critique = plan_data.get("critique", "No critique provided.")
            dependencies = plan_data.get("dependencies", [])
            self.log("info", f"Aura's Self-Critique: {critique}")
            final_plan = plan_data.get("final_plan", [])
            if not final_plan or not isinstance(final_plan, list):
                raise ValueError("Aura's final_plan was empty or malformed after self-critique.")

            if dependencies:
                deps_str = ", ".join(dependencies)
                final_plan.insert(0, f"Add the following dependencies to requirements.txt: {deps_str}")

            mission_log_service = self.service_manager.mission_log_service
            await mission_log_service.set_initial_plan(user_id, final_plan, user_idea)
            await self._post_chat_message(user_id, "Aura",
                                          "I've analyzed the request and created a production-ready plan. Review it in the 'Agent TODO' list and click 'Dispatch Aura' to begin.")
        except (ValueError, json.JSONDecodeError) as e:
            await self.handle_error(user_id, "Aura", f"Failed to create a valid plan: {e}.")
            self.log("error", f"Aura planner failure for user {user_id}. Raw response: {response_str}")

    def _get_relevant_plan_context(self, current_task_id: int, full_plan: List[Dict]) -> str:
        context_lines = []
        current_task_index = -1
        for i, task in enumerate(full_plan):
            if task.get('id') == current_task_id:
                current_task_index = i
                break
        if current_task_index == -1: return "Could not find the current task in the plan."
        if current_task_index > 0:
            prev_task = full_plan[current_task_index - 1]
            context_lines.append(
                f"Previous Task (ID {prev_task['id']}): {prev_task['description']} [Status: {'Done' if prev_task['done'] else 'Pending'}]")
        current_task = full_plan[current_task_index]
        context_lines.append(
            f"--> CURRENT TASK (ID {current_task['id']}): {current_task['description']} [Status: Pending]")
        if current_task_index < len(full_plan) - 1:
            next_task = full_plan[current_task_index + 1]
            context_lines.append(f"Next Task (ID {next_task['id']}): {next_task['description']} [Status: Pending]")
        return "\n".join(context_lines)

    async def _generate_code_for_task(self, user_id: str, path: str, task_description: str, user_idea: str,
                                      current_task_id: int) -> str:
        project_manager = self.service_manager.project_manager
        mission_log_service = self.service_manager.mission_log_service
        self.log("info", f"Generating code for '{path}'...")

        schema_content = project_manager.read_file('src/schemas.py') or "# src/schemas.py not found or is empty."
        models_content = project_manager.read_file('src/models.py') or "# src/models.py not found or is empty."
        schema_and_models_context = f"--- Contents of src/schemas.py ---\n{schema_content}\n\n--- Contents of src/models.py ---\n{models_content}"

        file_tree = "\n".join(
            sorted(project_manager.get_project_files().keys())) or "The project is currently empty."
        full_plan = mission_log_service.get_tasks()
        relevant_plan_context = self._get_relevant_plan_context(current_task_id, full_plan)

        prompt = CODER_PROMPT_STREAMING.format(
            path=path, task_description=task_description, file_tree=file_tree, user_idea=user_idea,
            relevant_plan_context=relevant_plan_context,
            schema_and_models_context=schema_and_models_context,
            MAESTRO_CODER_PHILOSOPHY_RULE=MAESTRO_CODER_PHILOSOPHY_RULE.strip(),
            TYPE_HINTING_RULE=TYPE_HINTING_RULE.strip(), DOCSTRING_RULE=DOCSTRING_RULE.strip(),
            CLEAN_CODE_RULE=CLEAN_CODE_RULE.strip(), RAW_CODE_OUTPUT_RULE=RAW_CODE_OUTPUT_RULE.strip())

        messages = [{"role": "user", "content": prompt}]
        self.refresh_llm_assignments()

        full_code = await self._unified_llm_streamer(int(user_id), "coder", messages, stream_to_user_socket_as='code_stream_chunk', file_path=path)

        code_block_regex = re.compile(r'''(?:python)?\n(.*?)\n'''', re.DOTALL)
        match = code_block_regex.search(full_code)
        return match.group(1).strip() if match else full_code.strip()

    async def run_strategic_replan(self, user_id: str, original_goal: str, failed_task: Dict, mission_log: List[Dict]):
        mission_log_service = self.service_manager.mission_log_service
        self.log("info", "Strategic re-plan initiated.")
        mission_log_str = "\n".join(
            [f"- ID {t['id']} ({'Done' if t['done'] else 'Pending'}): {t['description']}" for t in mission_log])
        failed_task_str = f"ID {failed_task['id']}: {failed_task['description']}"
        error_message = failed_task.get('last_error', 'No specific error message was recorded.')
        prompt = AURA_REPLANNER_PROMPT.format(
            user_goal=original_goal, mission_log=mission_log_str,
            failed_task=failed_task_str, error_message=error_message)
        messages = [{"role": "user", "content": prompt}]
        self.refresh_llm_assignments()

        response_str = await self._unified_llm_streamer(int(user_id), "planner", messages, is_json=True)

        if not response_str or response_str.startswith("Error:"):
            await self.handle_error(user_id, "Aura", response_str or "Re-planner returned an empty response.")
            return

        try:
            new_plan_data = self._parse_json_response(response_str)
            new_plan_steps = new_plan_data.get("plan", [])
            if not new_plan_steps:
                raise ValueError("Re-planner returned an empty or malformed plan.")
            await mission_log_service.replace_tasks_from_id(user_id, failed_task['id'], new_plan_steps)
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
        self.refresh_llm_assignments()
        summary = await self._unified_llm_streamer(int(user_id), "chat", messages)
        return summary.strip() if summary.strip() else "Mission accomplished!"

    async def _post_chat_message(self, user_id: str, sender: str, message: str, is_error: bool = False):
        if message and message.strip():
            msg_data = {
                "type": "aura_response" if sender.lower() == 'aura' else "system_log", "content": message}
            if is_error:
                msg_data["type"] = "system_log"
            await websocket_manager.broadcast_to_user(msg_data, user_id)

    async def handle_error(self, user_id: str, agent: str, error_msg: str):
        self.log("error", f"{agent} failed for user {user_id}: {error_msg}")
        await self._post_chat_message(user_id, "Aura", error_msg, is_error=True)

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "DevTeamService", level, message)
