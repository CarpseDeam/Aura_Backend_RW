# foundry/actions/streaming_actions.py
import logging
import re
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from src.event_bus import EventBus
from src.events import StreamCodeChunk
from src.prompts.coder import CODER_PROMPT_STREAMING
from src.prompts.master_rules import RAW_CODE_OUTPUT_RULE, TYPE_HINTING_RULE, DOCSTRING_RULE, CLEAN_CODE_RULE

if TYPE_CHECKING:
    from src.core.managers import ProjectManager
    from src.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


def _robustly_clean_llm_output(content: str) -> str:
    """Cleans markdown and other noise from the LLM's code output."""
    content = content.strip()
    code_block_regex = re.compile(r'```(?:python)?\n(.*?)\n```', re.DOTALL)
    match = code_block_regex.search(content)
    if match:
        return match.group(1).strip()
    return content


async def stream_and_write_file(path: str, task_description: str, project_manager: "ProjectManager",
                                llm_client: "LLMClient", event_bus: EventBus) -> str:
    """
    The definitive action for all AI code generation. It streams the response from the LLM
    to the GUI in real-time and saves the final, cleaned code to a file.
    """
    logger.info(f"Streaming and writing file for task: {task_description[:60]}...")

    file_path_obj = Path(path)
    relative_path = str(file_path_obj)  # Assume path is already relative from runner

    # Get project context for the Coder prompt
    file_tree = "\n".join(sorted(list(project_manager.get_project_files().keys()))) or "The project is currently empty."

    prompt = CODER_PROMPT_STREAMING.format(
        path=relative_path,
        task_description=task_description,
        file_tree=file_tree,
        TYPE_HINTING_RULE=TYPE_HINTING_RULE.strip(),
        DOCSTRING_RULE=DOCSTRING_RULE.strip(),
        CLEAN_CODE_RULE=CLEAN_CODE_RULE.strip(),
        RAW_CODE_OUTPUT_RULE=RAW_CODE_OUTPUT_RULE.strip()
    )

    provider, model = llm_client.get_model_for_role("coder")
    if not provider or not model:
        return "Error: No model configured for 'coder' role."

    logger.info(f"Streaming code for '{relative_path}' from {provider}/{model}...")

    raw_code_accumulator = []
    # Clear the target tab in the code viewer
    event_bus.emit("stream_code_chunk", StreamCodeChunk(filename=relative_path, chunk="", is_first_chunk=True))
    await asyncio.sleep(0.01)

    try:
        async for chunk in llm_client.stream_chat(provider, model, prompt, "coder"):
            event_bus.emit("stream_code_chunk", StreamCodeChunk(filename=relative_path, chunk=chunk))
            raw_code_accumulator.append(chunk)
            await asyncio.sleep(0.01)

        full_raw_code = "".join(raw_code_accumulator)
        cleaned_code = _robustly_clean_llm_output(full_raw_code)

        if not cleaned_code.strip():
            return f"Error: AI returned empty code for task: {task_description}"

        file_path_obj.parent.mkdir(parents=True, exist_ok=True)
        file_path_obj.write_text(cleaned_code, encoding='utf-8')

        return f"Successfully streamed and wrote {len(cleaned_code)} bytes to '{relative_path}'."

    except Exception as e:
        error_msg = f"An unexpected error occurred during code streaming: {e}"
        logger.exception(error_msg)
        return error_msg