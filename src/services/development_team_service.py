# src/services/development_team_service.py
from __future__ import annotations
import json
import re
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from src.event_bus import EventBus
from src.prompts.creative import AURA_PLANNER_PROMPT, AURA_REPLANNER_PROMPT, AURA_MISSION_SUMMARY_PROMPT
from src.prompts.coder import CODER_PROMPT
from src.prompts.master_rules import JSON_OUTPUT_RULE, SENIOR_ARCHITECT_HEURISTIC_RULE
from src.events import PlanReadyForReview, PostChatMessage

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

    def _post_chat_message(self, sender: str, message: str, is_error: bool = False):
        if message and message.strip():
            self.event_bus.emit("post_chat_message", PostChatMessage(sender, message, is_error))

    def _parse_json_response(self, response: str) -> dict:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in the response. Raw response: {response}")
        return json.loads(match.group(0))

    async def run_aura_planner_workflow(self, user_idea: str, conversation_history: list):
        """
        The main entry point for a user request. It generates a new plan.
        """
        self.log("info", f"Aura planner workflow initiated for: '{user_idea[:50]}...'")

        provider, model = self.llm_client.get_model_for_role("planner")
        if not provider or not model:
            self.handle_error("Aura", "No 'planner' model configured.")
            return

        self.event_bus.emit("agent_status_changed", "Aura", "Formulating an efficient plan...", "fa5s.lightbulb")
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
            self.mission_log_service.set_initial_plan(plan_steps, user_idea)
            self._post_chat_message("Aura",
                                    "I've created a plan to build your project. Please review it in the 'Agent TODO' list and click 'Dispatch Aura' to begin execution.")
            self.event_bus.emit("plan_ready_for_review", PlanReadyForReview())
        except (ValueError, json.JSONDecodeError) as e:
            self.handle_error("Aura", f"Failed to create a valid plan: {e}.")
            self.log("error", f"Aura planner failure. Raw response: {response_str}")

    async def run_coding_task(self, task: Dict[str, any], last_error: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Asks the Coder AI to translate a single natural language task into an
        executable tool call, providing it with full context including past attempts.
        """
        if task.get("tool_call"):
            self.log("info", f"Using pre-defined tool call for task: {task['description']}")
            return task["tool_call"]

        current_task_description = task['description']
        self.log("info", f"Coder translating task to tool call: {current_task_description}")
        self.event_bus.emit("agent_status_changed", "Aura", f"Coding task: {current_task_description}...", "fa5s.cogs")

        # Get history from Mission Log
        log_tasks = self.mission_log_service.get_tasks()
        mission_log_history = "\n".join(
            [f"- ID {t['id']} ({'Done' if t['done'] else 'Pending'}): {t['description']}" for t in log_tasks])
        if not mission_log_history:
            mission_log_history = "The mission log is empty. This is the first task."

        if last_error:
            current_task_description += f"\n\n**PREVIOUS ATTEMPT FAILED!** The last attempt to perform this task failed with the following error: `{last_error}`. You MUST analyze this error and try a different tool or different arguments to succeed."

        # Get RAG context
        vector_context = "No existing code snippets were found."
        if self.vector_context_service and self.vector_context_service.collection.count() > 0:
            try:
                retrieved_chunks = self.vector_context_service.query(current_task_description, n_results=5)
                if retrieved_chunks:
                    context_parts = [
                        f"```python\n# From: {chunk['metadata'].get('file_path', 'N/A')}\n{chunk['document']}\n```" for
                        chunk in retrieved_chunks]
                    vector_context = "\n\n".join(context_parts)
            except Exception as e:
                self.log("error", f"Failed to query vector context: {e}")

        # Get other context
        file_structure = "\n".join(
            sorted(self.project_manager.get_project_files().keys())) or "The project is currently empty."
        available_tools = json.dumps(self.foundry_manager.get_llm_tool_definitions(), indent=2)

        prompt = CODER_PROMPT.format(
            current_task=current_task_description,
            mission_log=mission_log_history,
            available_tools=available_tools,
            file_structure=file_structure,
            relevant_code_snippets=vector_context,
            JSON_OUTPUT_RULE=JSON_OUTPUT_RULE.strip()
        )

        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.log("error", "No 'coder' model configured.")
            return None

        response_str = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "coder")])

        try:
            tool_call = self._parse_json_response(response_str)
            if "tool_name" not in tool_call or "arguments" not in tool_call:
                raise ValueError("Coder response must be a JSON object with 'tool_name' and 'arguments' keys.")
            return tool_call
        except (ValueError, json.JSONDecodeError) as e:
            self.log("error", f"Coder generation failure. Raw response: {response_str}. Error: {e}")
            return None

    async def run_strategic_replan(self, original_goal: str, failed_task: Dict, mission_log: List[Dict]):
        """
        Invokes the Re-Planner AI to create a new plan when a task fails repeatedly.
        """
        self.log("info", "Strategic re-plan initiated.")
        self.event_bus.emit("agent_status_changed", "Aura", "Hitting a roadblock. Rethinking the plan...",
                            "fa5s.search")

        mission_log_str = "\n".join(
            [f"- ID {t['id']} ({'Done' if t['done'] else 'Pending'}): {t['description']}" for t in mission_log])
        failed_task_str = f"ID {failed_task['id']}: {failed_task['description']}"
        error_message = failed_task.get('last_error', 'No specific error message was recorded.')

        prompt = AURA_REPLANNER_PROMPT.format(
            user_goal=original_goal,
            mission_log=mission_log_str,
            failed_task=failed_task_str,
            error_message=error_message
        )

        provider, model = self.llm_client.get_model_for_role("planner")
        if not provider or not model:
            self.handle_error("Aura", "No 'planner' model available for re-planning.")
            return

        response_str = "".join(
            [chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "planner")])

        try:
            new_plan_data = self._parse_json_response(response_str)
            new_plan_steps = new_plan_data.get("plan", [])
            if not new_plan_steps:
                raise ValueError("Re-planner returned an empty or malformed plan.")

            self.mission_log_service.replace_tasks_from_id(failed_task['id'], new_plan_steps)
            self.log("success", f"Successfully replaced failed task with a new plan of {len(new_plan_steps)} steps.")
        except (ValueError, json.JSONDecodeError) as e:
            self.handle_error("Aura", f"I failed to create a valid recovery plan: {e}")
            self.log("error", f"Aura re-planner failure. Raw response: {response_str}")

    async def generate_mission_summary(self, completed_tasks: List[Dict]) -> str:
        """Generates a final summary of the completed mission."""
        self.log("info", "Generating mission summary.")
        self.event_bus.emit("agent_status_changed", "Aura", "Generating mission summary...", "fa5s.pen-fancy")

        task_descriptions = "\n".join([f"- {task['description']}" for task in completed_tasks if task['done']])
        if not task_descriptions:
            return "Mission accomplished, although no specific tasks were marked as completed in the log."

        prompt = AURA_MISSION_SUMMARY_PROMPT.format(completed_tasks=task_descriptions)

        provider, model = self.llm_client.get_model_for_role("chat")
        if not provider or not model:
            self.log("error", "No 'chat' model available for summary generation.")
            return "Mission accomplished!"

        summary = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "chat")])
        return summary.strip() if summary.strip() else "Mission accomplished!"

    def handle_error(self, agent: str, error_msg: str):
        self.log("error", f"{agent} failed: {error_msg}")
        self.event_bus.emit("agent_status_changed", "Aura", "Failed", "fa5s.exclamation-triangle")
        self._post_chat_message("Aura", error_msg, is_error=True)

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "DevTeamService", level, message)