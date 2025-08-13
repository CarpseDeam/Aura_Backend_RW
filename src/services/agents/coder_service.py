# services/agents/coder_service.py
import json
import re
from typing import Dict, Optional

from event_bus import EventBus
from core.llm_client import LLMClient
from src.services.vector_context_service import VectorContextService
from core.managers.project_manager import ProjectManager
from src.foundry import FoundryManager
from prompts import CODER_PROMPT
from prompts.master_rules import JSON_OUTPUT_RULE


class CoderService:
    """
    A specialized service responsible for translating a task into a single,
    executable tool call by prompting an LLM with RAG context.
    """

    def __init__(
        self,
        event_bus: EventBus,
        llm_client: LLMClient,
        vector_context_service: VectorContextService,
        project_manager: ProjectManager,
        foundry_manager: FoundryManager,
    ):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.vector_context_service = vector_context_service
        self.project_manager = project_manager
        self.foundry_manager = foundry_manager

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "CoderService", level, message)

    def _parse_json_response(self, response: str) -> dict:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in the response.")
        return json.loads(match.group(0))

    async def run_coding_task(
        self,
        current_task: str,
    ) -> Optional[Dict[str, str]]:
        """
        Translates a single task into a tool call using an LLM with RAG context.
        """
        self.log("info", f"Translating task to tool call: {current_task}")
        self.event_bus.emit("agent_status_changed", "Coder", f"Planning action for: {current_task}...", "fa5s.cogs")

        # 1. Get relevant context using RAG
        relevant_context = "No existing code snippets were found. You are likely creating a new file or starting a new project."
        try:
            if self.vector_context_service and self.vector_context_service.collection.count() > 0:
                retrieved_chunks = self.vector_context_service.query(current_task, n_results=5)
                if retrieved_chunks:
                    context_parts = ["Here are the most relevant code snippets based on the task:\n"]
                    for chunk in retrieved_chunks:
                        metadata = chunk['metadata']
                        source_info = f"From file: {metadata.get('file_path', 'N/A')} ({metadata.get('node_type', 'N/A')}: {metadata.get('node_name', 'N/A')})"
                        context_parts.append(f"```python\n# {source_info}\n{chunk['document']}\n```")
                    relevant_context = "\n\n".join(context_parts)
            else:
                self.log("warning", "Vector database is empty. Proceeding without RAG context.")
        except Exception as e:
            self.log("error", f"Failed to query vector context: {e}")
            relevant_context = f"Error: Could not retrieve context from the vector database. Details: {e}"

        # 2. Get the file tree and available tools
        file_structure = "\n".join(sorted(list(self.project_manager.get_project_files().keys()))) or "The project is currently empty."
        available_tools = json.dumps(self.foundry_manager.get_llm_tool_definitions(), indent=2)

        # 3. Build the prompt
        prompt = CODER_PROMPT.format(
            current_task=current_task,
            available_tools=available_tools,
            file_structure=file_structure,
            relevant_code_snippets=relevant_context,
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