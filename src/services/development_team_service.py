# src/services/development_team_service.py
from __future__ import annotations

import ast
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
from src.prompts.creative import (ARCHITECT_PROMPT, SEQUENCER_PROMPT, AURA_REPLANNER_PROMPT,
                                  AURA_MISSION_SUMMARY_PROMPT)
from src.prompts.intent import INTENT_DETECTION_PROMPT
from src.prompts.coder import CODER_PROMPT_STREAMING
from src.prompts.master_rules import SENIOR_ARCHITECT_HEURISTIC_RULE, TYPE_HINTING_RULE, DOCSTRING_RULE, \
    CLEAN_CODE_RULE, MAESTRO_CODER_PHILOSOPHY_RULE, RAW_CODE_OUTPUT_RULE
from src.prompts.companion import COMPANION_PROMPT
from src.db import crud
from src.services import mission_control
from src.prompts.polish import METICULOUS_LINTER_PROMPT

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

    async def unified_llm_streamer(self, user_id: int, role: str, messages: List[Dict[str, Any]],
                                   is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None,
                                   stream_to_user_socket_as: Optional[str] = None,
                                   file_path: Optional[str] = None) -> str:
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
                        if not await mission_control.is_mission_running(str(user_id)):
                            self.log("info",
                                     f"Stop request received during code generation for user {user_id}. Halting stream.")
                            await self._post_chat_message(str(user_id), "Conductor",
                                                          "Code generation halted by user request.")
                            return "Error: Code generation was cancelled by the user."

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

    def parse_json_response(self, response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r'''json\s*(\{.*?\})\s*''', response, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                raise ValueError(f"No JSON object found in the response. Raw response: {response}")
            return json.loads(match.group(0))

    async def determine_user_intent(self, user_id: str, user_prompt: str, conversation_history: list) -> str:
        self.log("info", f"Determining intent for user {user_id}: '{user_prompt[:50]}...'")
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
        prompt = INTENT_DETECTION_PROMPT.format(
            conversation_history=history_str,
            user_prompt=user_prompt
        )
        messages = [{"role": "user", "content": prompt}]
        self.refresh_llm_assignments()
        response_str = await self.unified_llm_streamer(int(user_id), "planner", messages, is_json=True)
        if not response_str or response_str.startswith("Error:"):
            await self.handle_error(user_id, "IntentDetector",
                                    response_str or "Intent detector returned an empty response.")
            return "CHAT"
        try:
            intent_data = self.parse_json_response(response_str)
            intent = intent_data.get("intent", "CHAT").upper()
            if intent not in ["PLAN", "CHAT"]:
                self.log("warning", f"Intent detector returned invalid intent: {intent}. Defaulting to CHAT.")
                return "CHAT"
            self.log("info", f"Detected user intent: {intent}")
            return intent
        except (ValueError, json.JSONDecodeError) as e:
            await self.handle_error(user_id, "IntentDetector", f"Failed to parse intent JSON: {e}. Raw: {response_str}")
            return "CHAT"

    async def run_companion_chat(self, user_id: str, user_prompt: str, conversation_history: list) -> str:
        self.log("info", f"Companion chat initiated for user {user_id}: '{user_prompt[:50]}...'")
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
        prompt = COMPANION_PROMPT.format(conversation_history=history_str, user_prompt=user_prompt)
        messages = [{"role": "user", "content": prompt}]
        self.refresh_llm_assignments()
        response_str = await self.unified_llm_streamer(int(user_id), "chat", messages)
        if response_str.startswith("Error:"):
            await self.handle_error(user_id, "Companion", response_str)
            return "I'm sorry, I seem to be having trouble connecting to my creative core right now."
        return response_str

    async def run_aura_planner_workflow(self, user_id: str, user_idea: str, conversation_history: list,
                                        project_name: str):
        """
        Orchestrates the new two-step planning assembly line: Architect -> Sequencer.
        """
        self.log("info", f"Aura planning assembly line initiated for user {user_id}: '{user_idea[:50]}...'")
        self.refresh_llm_assignments()

        # --- Phase 1: Architect ---
        architect_prompt = ARCHITECT_PROMPT.format(user_idea=user_idea, project_name=project_name)
        messages = [{"role": "user", "content": architect_prompt}]
        blueprint_response = await self.unified_llm_streamer(int(user_id), "planner", messages, is_json=True)

        if not blueprint_response or blueprint_response.strip().startswith("Error:"):
            error_content = blueprint_response or "The Architect AI returned an empty or invalid response."
            await self.handle_error(user_id, "Architect", error_content)
            return

        try:
            blueprint_data = self.parse_json_response(blueprint_response)
            final_blueprint = blueprint_data.get("final_blueprint")
            if not final_blueprint or not isinstance(final_blueprint, dict):
                raise ValueError("Architect's final_blueprint was missing or malformed.")
        except (ValueError, json.JSONDecodeError) as e:
            await self.handle_error(user_id, "Architect", f"Failed to create a valid blueprint: {e}.")
            self.log("error", f"Architect failure for user {user_id}. Raw response: {blueprint_response}")
            return

        # --- Phase 2: Sequencer ---
        await websocket_manager.broadcast_to_user(
            {"type": "phase", "content": "Sequencer is generating the detailed task list..."}, str(user_id))
        sequencer_prompt = SEQUENCER_PROMPT.format(blueprint=json.dumps(final_blueprint, indent=2))
        messages = [{"role": "user", "content": sequencer_prompt}]
        plan_response = await self.unified_llm_streamer(int(user_id), "planner", messages, is_json=True)

        if not plan_response or plan_response.strip().startswith("Error:"):
            error_content = plan_response or "The Sequencer AI returned an empty or invalid response."
            await self.handle_error(user_id, "Sequencer", error_content)
            return

        try:
            plan_data = self.parse_json_response(plan_response)
            final_plan_steps = plan_data.get("final_plan", [])
            if not final_plan_steps or not isinstance(final_plan_steps, list):
                raise ValueError("Sequencer's final_plan was empty or malformed.")

            dependencies = final_blueprint.get("dependencies", [])
            if dependencies:
                deps_str = ", ".join(dependencies)
                final_plan_steps.insert(0, f"Add the following dependencies to requirements.txt: {deps_str}")

            mission_log_service = self.service_manager.mission_log_service
            await mission_log_service.set_initial_plan(user_id, final_plan_steps, user_idea)
            await self._post_chat_message(user_id, "Aura",
                                          "I've created a plan. Review it in 'Agent TODO' and click 'Dispatch Aura' to begin.")
        except (ValueError, json.JSONDecodeError) as e:
            await self.handle_error(user_id, "Sequencer", f"Failed to create a valid plan: {e}.")
            self.log("error", f"Sequencer failure for user {user_id}. Raw response: {plan_response}")

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

    async def generate_code_for_task(self, user_id: str, path: str, task_description: str, user_idea: str,
                                      current_task_id: int) -> str:
        project_manager = self.service_manager.project_manager
        mission_log_service = self.service_manager.mission_log_service
        self.log("info", f"Generating code for '{path}'...")
        schema_content = project_manager.read_file('src/schemas.py') or "# src/schemas.py not found or is empty."
        models_content = project_manager.read_file('src/models.py') or "# src/models.py not found or is empty."
        schema_and_models_context = f"--- Contents of src/schemas.py ---\n{schema_content}\n\n--- Contents of src/models.py ---\n{models_content}"
        file_tree = "\n".join(sorted(project_manager.get_project_files().keys())) or "The project is currently empty."
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
        full_code = await self.unified_llm_streamer(int(user_id), "coder", messages,
                                                     stream_to_user_socket_as='code_stream_chunk', file_path=path)
        if full_code.startswith("Error:"):
            return full_code
        code_block_regex = re.compile(r'```(?:python\n)?(.*?)```', re.DOTALL)
        match = code_block_regex.search(full_code)
        clean_code = match.group(1).strip() if match else full_code.strip()
        if not clean_code:
            return f"Error: The AI failed to generate any code for '{path}'. The response was empty."
        try:
            ast.parse(clean_code)
            self.log("success", f"Generated code for '{path}' is syntactically valid.")
            return clean_code
        except SyntaxError as e:
            return f"Error: AI-generated code for '{path}' has a syntax error: {e}"

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
        response_str = await self.unified_llm_streamer(int(user_id), "planner", messages, is_json=True)
        if not response_str or response_str.startswith("Error:"):
            await self.handle_error(user_id, "Aura", response_str or "Re-planner returned an empty response.")
            return
        try:
            new_plan_data = self.parse_json_response(response_str)
            new_plan_steps = new_plan_data.get("plan", [])
            if not new_plan_steps:
                raise ValueError("Re-planner returned an empty or malformed plan.")
            await mission_log_service.replace_tasks_from_id(user_id, failed_task['id'], new_plan_steps)
            self.log("success", f"Successfully replaced failed task for user {user_id} with a new plan.")
            await self._post_chat_message(user_id, "Aura", "I have a new plan. Resuming execution.")
        except (ValueError, json.JSONDecodeError) as e:
            await self.handle_error(user_id, "Aura", f"I failed to create a valid recovery plan: {e}")
            self.log("error", f"Aura re-planner failure for user {user_id}. Raw response: {response_str}")

    async def run_final_polish_linter(self, user_id: str, user_idea: str, file_tree: str, git_diff: str) -> List[
        Dict[str, str]]:
        """
        Invokes the Meticulous Linter AI to find and suggest fixes for new code.
        """
        self.log("info", "Running Final Polish check on newly generated code...")
        await self._post_chat_message(user_id, "Conductor",
                                      "Code generation complete. Performing final quality review...")

        prompt = METICULOUS_LINTER_PROMPT.format(
            user_idea=user_idea,
            file_tree=file_tree,
            git_diff=git_diff
        )
        messages = [{"role": "user", "content": prompt}]
        self.refresh_llm_assignments()

        response_str = await self.unified_llm_streamer(int(user_id), "planner", messages, is_json=True)

        if not response_str or response_str.startswith("Error:"):
            await self.handle_error(user_id, "FinalPolish", response_str or "The Linter AI returned an empty response.")
            return []

        try:
            fix_data = self.parse_json_response(response_str)
            fixes = fix_data.get("fixes", [])
            if not isinstance(fixes, list):
                raise ValueError("The 'fixes' key must be a list.")

            if fixes:
                self.log("success", f"Final Polish found {len(fixes)} issue(s) to correct.")
                await self._post_chat_message(user_id, "Conductor",
                                              f"Found {len(fixes)} small bug(s). Applying automated patches...")
            else:
                self.log("success", "Final Polish found no issues. The code is clean!")
                await self._post_chat_message(user_id, "Conductor", "Final quality review passed with no issues.")

            return fixes
        except (ValueError, json.JSONDecodeError) as e:
            await self.handle_error(user_id, "FinalPolish", f"Failed to parse Linter AI JSON: {e}. Raw: {response_str}")
            return []

    async def generate_mission_summary(self, user_id: str, completed_tasks: List[Dict]) -> str:
        task_descriptions = "\n".join([f"- {task['description']}" for task in completed_tasks if task['done']])
        if not task_descriptions:
            return "Mission accomplished!"
        prompt = AURA_MISSION_SUMMARY_PROMPT.format(completed_tasks=task_descriptions)
        messages = [{"role": "user", "content": prompt}]
        self.refresh_llm_assignments()
        summary = await self.unified_llm_streamer(int(user_id), "chat", messages)
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