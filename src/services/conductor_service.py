# src/services/conductor_service.py
import logging
import asyncio
import json
import re
import ast
from typing import Dict, Optional, List, Any, TYPE_CHECKING
from pathlib import Path

from src.core.websockets import websocket_manager
from src.services import mission_control
from src.event_bus import EventBus
from src.prompts import CODER_PROMPT, JSON_OUTPUT_RULE

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
        self.service_manager = service_manager
        self.original_user_goal = ""
        logger.info("ConductorService initialized.")

    async def _get_tool_call_for_task(self, user_id: str, task: Dict[str, Any], last_error: Optional[str] = None) -> \
    Optional[Dict[str, Any]]:
        mission_log_service = self.service_manager.mission_log_service
        foundry_manager = self.service_manager.foundry_manager
        development_team_service = self.service_manager.development_team_service
        project_manager = self.service_manager.project_manager
        vector_context_service = self.service_manager.vector_context_service

        current_task_description = task['description']
        log_tasks = mission_log_service.get_tasks()
        mission_log_history = "\n".join(
            [f"- ID {t['id']} ({'Done' if t['done'] else 'Pending'}): {t['description']}" for t in log_tasks])
        if not mission_log_history:
            mission_log_history = "This is the first task."
        if last_error:
            current_task_description += f"\n\n**PREVIOUS ATTEMPT FAILED!** Last error: `{last_error}`. You MUST try a different approach."

        active_file_context_parts = []
        path_pattern = re.compile(r'([\w./-]+\.[\w]+)')
        found_paths = set(path_pattern.findall(current_task_description))

        if found_paths:
            for relative_path_str in sorted(list(found_paths)):
                if '/' not in relative_path_str and not relative_path_str.endswith(('.py', '.md', '.txt', '.json', '.toml')):
                    continue

                file_content = project_manager.read_file(relative_path_str)
                context_header = f"**Context for `{relative_path_str}`:**"
                if file_content:
                    self.log("info", f"Context Weaver: Found and read active file: {relative_path_str}")
                    context_parts = [context_header]
                    if relative_path_str.endswith(".py"):
                        try:
                            tree = ast.parse(file_content)
                            imports, functions, classes = set(), set(), set()
                            for node in tree.body:
                                if isinstance(node, ast.Import):
                                    for alias in node.names: imports.add(alias.name)
                                elif isinstance(node, ast.ImportFrom):
                                    if node.module: imports.add(node.module)
                                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    functions.add(node.name)
                                elif isinstance(node, ast.ClassDef):
                                    classes.add(node.name)

                            if imports: context_parts.append(f"- Imports: {', '.join(sorted(list(imports)))}")
                            if functions: context_parts.append(f"- Functions: {', '.join(sorted(list(functions)))}")
                            if classes: context_parts.append(f"- Classes: {', '.join(sorted(list(classes)))}")
                            if not any([imports, functions, classes]):
                                context_parts.append("- The file is valid Python but contains no top-level definitions.")
                            active_file_context_parts.append("\n".join(context_parts))
                        except (SyntaxError, TypeError) as e:
                            self.log("warning", f"Context Weaver: Could not parse {relative_path_str}, providing raw content. Error: {e}")
                            active_file_context_parts.append(f"{context_header}\n```\n{file_content[:1000]}...\n```")
                    else:
                        active_file_context_parts.append(f"{context_header}\n```\n{file_content[:1000]}...\n```")
                else:
                    active_file_context_parts.append(f"{context_header}\n- This file does not exist yet. You may need to create it.")

        active_file_context = "\n\n".join(active_file_context_parts)
        if not active_file_context:
            active_file_context = "No specific file context was identified for this task. You might be creating a new file or directory."

        vector_context = "Vector context (RAG) is currently disabled."
        if vector_context_service and vector_context_service.collection and vector_context_service.collection.count() > 0:
            retrieved_chunks = await vector_context_service.query(current_task_description, n_results=5)
            if retrieved_chunks:
                context_parts = ["Here are the most relevant code snippets based on the task:\n"]
                for chunk in retrieved_chunks:
                    metadata = chunk['metadata']
                    source_info = f"From file: {metadata.get('file_path', 'N/A')} ({metadata.get('node_type', 'N/A')}: {metadata.get('node_name', 'N/A')})"
                    context_parts.append(f"```python\n# {source_info}\n{chunk['document']}\n```")
                vector_context = "\n\n".join(context_parts)

        file_structure = "\n".join(sorted(project_manager.get_project_files().keys())) or "The project is currently empty."
        available_tools_json = json.dumps(foundry_manager.get_llm_tool_definitions(), indent=2)

        prompt = CODER_PROMPT.format(
            current_task=current_task_description,
            mission_log=mission_log_history,
            file_structure=file_structure,
            active_file_context=active_file_context,
            available_tools=available_tools_json,
            relevant_code_snippets=vector_context,
            JSON_OUTPUT_RULE=JSON_OUTPUT_RULE.strip()
        )

        messages = [{"role": "user", "content": prompt}]
        response_str = await development_team_service._unified_llm_streamer(int(user_id), "coder", messages, is_json=True)

        if response_str.startswith("Error:"):
            self.log("error", f"Conductor's LLM call failed. Details: {response_str}")
            return None

        try:
            tool_call = development_team_service._parse_json_response(response_str)
            if "tool_name" not in tool_call or "arguments" not in tool_call:
                raise ValueError("Response must be JSON with 'tool_name' and 'arguments'.")
            if tool_call.get("tool_name") == "write_file":
                args = tool_call.get("arguments", {})
                if not args.get("content") and args.get("task_description"):
                    generated_code = await development_team_service._generate_code_for_task(
                        user_id, args.get("path"), args.get("task_description"), self.original_user_goal, task['id']
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
        await mission_control.set_mission_running(user_id)
        self.original_user_goal = self.service_manager.mission_log_service.get_initial_goal()
        try:
            await self.execute_mission(user_id)
        finally:
            await mission_control.set_mission_finished(user_id)
            await websocket_manager.broadcast_to_user({"type": "agent_status", "status": "idle"}, user_id)
            self.log("info", f"Conductor finished mission for user {user_id}.")

    async def _apply_polish_fixes(self, user_id: str, fixes: List[Dict[str, str]]) -> bool:
        project_manager = self.service_manager.project_manager
        all_successful = True
        for fix in fixes:
            try:
                file_path_str = fix["file_path"]
                original_snippet = fix["original_code_snippet"]
                fixed_snippet = fix["fixed_code_snippet"]
                current_content = project_manager.read_file(file_path_str)
                if current_content is None:
                    self.log("error", f"Final Polish: Cannot apply fix. File not found: {file_path_str}")
                    all_successful = False
                    continue
                if original_snippet not in current_content:
                    self.log("warning", f"Final Polish: Snippet to be replaced not found in {file_path_str}. Skipping fix.")
                    continue
                new_content = current_content.replace(original_snippet, fixed_snippet, 1)
                project_manager.write_file(file_path_str, new_content)
                self.log("info", f"Final Polish: Applied fix to {file_path_str}")
                await self._post_chat_message(user_id, "Conductor", f"Patched bug in `{file_path_str}`.")
            except Exception as e:
                self.log("error", f"Final Polish: Failed to apply fix to {fix.get('file_path')}. Error: {e}")
                all_successful = False
        return all_successful

    async def _run_final_polish_check(self, user_id: str):
        project_manager = self.service_manager.project_manager
        development_team_service = self.service_manager.development_team_service
        if project_manager.git_manager and project_manager.git_manager.repo:
            project_manager.git_manager.repo.git.add(A=True)
        git_diff = project_manager.get_git_diff()
        if not git_diff or not git_diff.strip():
            self.log("info", "No code changes detected. Skipping final polish.")
            return
        file_tree = "\n".join(sorted(project_manager.get_project_files().keys()))
        fixes = await development_team_service.run_final_polish_linter(
            user_id, self.original_user_goal, file_tree, git_diff
        )
        if fixes:
            await self._apply_polish_fixes(user_id, fixes)
            if project_manager.git_manager:
                project_manager.git_manager.commit_staged_files("fix(agent): apply automated polish fixes")

    async def execute_mission(self, user_id: str):
        mission_log_service = self.service_manager.mission_log_service
        tool_runner_service = self.service_manager.tool_runner_service
        try:
            await self._post_chat_message(user_id, "Conductor", "Mission dispatched. Beginning autonomous execution.")
            await websocket_manager.broadcast_to_user({"type": "agent_status", "status": "thinking"}, user_id)
            while True:
                if not await mission_control.is_mission_running(user_id):
                    self.log("info", f"Mission for user {user_id} was stopped by request.")
                    await self._post_chat_message(user_id, "Conductor", "Mission execution halted by user.")
                    break
                pending_tasks = mission_log_service.get_tasks(done=False)
                if not pending_tasks:
                    await self._run_final_polish_check(user_id)
                    await self._handle_mission_completion(user_id)
                    break
                current_task = pending_tasks[0]
                await websocket_manager.broadcast_to_user(
                    {"type": "active_task_updated", "content": {"taskId": current_task['id']}},
                    user_id
                )
                retry_count = 0
                task_succeeded = False
                while retry_count <= self.MAX_RETRIES_PER_TASK:
                    if not await mission_control.is_mission_running(user_id):
                        break
                    self.log("info", f"Executing task {current_task['id']}: {current_task['description']}")
                    tool_call = await self._get_tool_call_for_task(user_id, current_task, current_task.get('last_error'))
                    if not tool_call:
                        error_msg = f"Could not determine a tool call for task: '{current_task['description']}'"
                        current_task['last_error'] = error_msg
                        retry_count += 1
                        continue
                    result = await tool_runner_service.run_tool_by_dict(tool_call, user_id=user_id)
                    result_is_error, error_message = self._is_result_an_error(result)
                    if not result_is_error:
                        await mission_log_service.mark_task_as_done(user_id, current_task['id'])
                        await self._post_chat_message(user_id, "Conductor", f"Task completed: {current_task['description']}")
                        task_succeeded = True
                        break
                    else:
                        current_task['last_error'] = error_message
                        retry_count += 1
                        self.log("warning", f"Task {current_task['id']} failed. Error: {error_message}.")
                        await self._post_chat_message(user_id, "Conductor", f"Task failed, retrying. Error: {error_message}", is_error=True)
                if not task_succeeded and await mission_control.is_mission_running(user_id):
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
        await self.service_manager.development_team_service.run_strategic_replan(
            user_id, self.original_user_goal, failed_task, self.service_manager.mission_log_service.get_tasks()
        )

    async def _handle_mission_completion(self, user_id: str):
        self.log("success", f"Mission Accomplished for user {user_id}!")
        summary = await self.service_manager.development_team_service.generate_mission_summary(
            user_id, self.service_manager.mission_log_service.get_tasks()
        )
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