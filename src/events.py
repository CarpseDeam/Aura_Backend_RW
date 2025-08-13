# events.py
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# --- Core Application & User Input Events ---

@dataclass
class UserPromptEntered:
    """Published when the user submits a request via the main chat input."""
    prompt_text: str
    conversation_history: List[Dict[str, Any]]
    image_bytes: Optional[bytes] = None
    image_media_type: Optional[str] = None
    code_context: Optional[Dict[str, str]] = None

@dataclass
class UserCommandEntered:
    """Published when the user submits a slash command."""
    command: str
    args: List[str]

@dataclass
class AppStateChanged:
    """Published by AppStateService when the state (BOOTSTRAP/MODIFY) changes."""
    new_state: Any # Should be AppState enum
    project_name: Optional[str] = None

@dataclass
class NewSessionRequested:
    """Published when the user requests to start a new, clean session."""
    pass

# --- AI Agent & Workflow Events ---

@dataclass
class AgentStatusChanged:
    """Published by AI agents to update the main status bar."""
    agent_name: str
    status_text: str
    icon_name: str

@dataclass
class PostChatMessage:
    """Requests that a message be posted to the main chat log from a service."""
    sender: str
    message: str
    is_error: bool = False

@dataclass
class AIWorkflowFinished:
    """Published when any main AI workflow (build or chat) completes or fails."""
    pass

@dataclass
class PlanReadyForReview:
    """Published by the Dev Team when the Architect's plan is in the Mission Log."""
    pass

# --- Code Generation & Streaming Events ---

@dataclass
class StreamCodeChunk:
    """Published by the Coder agent with a piece of generated code for a file."""
    filename: str
    chunk: str
    is_first_chunk: bool = False

@dataclass
class CodeGenerationComplete:
    """Published by the DevelopmentTeamService when all files have been generated."""
    generated_files: Dict[str, str]

# --- Mission Log & Execution Events ---

@dataclass
class MissionPlanReady:
    """Published by the Finalizer with a complete, tool-based execution plan."""
    plan: List[Dict[str, Any]]

@dataclass
class MissionDispatchRequest:
    """Published by the Mission Log UI when the user clicks 'Dispatch'."""
    pass

@dataclass
class MissionLogUpdated:
    """Published by the MissionLogService when tasks are added, removed, or changed."""
    tasks: List[Dict[str, Any]]

@dataclass
class MissionAccomplished:
    """Published by the Conductor when all tasks and tests are successfully completed."""
    pass

# --- Tool & Foundry Events ---

@dataclass
class DirectToolInvocationRequest:
    """For directly calling a tool, bypassing the AI workflow (e.g., from a context menu)."""
    tool_id: str
    params: Dict[str, Any]

@dataclass
class ToolsModified:
    """Published by the create_new_tool action to signal a need for a tool rescan."""
    pass

@dataclass
class ToolCallInitiated:
    """Published by the ToolRunner when a tool is about to be executed."""
    widget_id: int
    tool_name: str
    params: Dict[str, Any]

@dataclass
class ToolCallCompleted:
    """Published by the ToolRunner after a tool has been executed."""
    widget_id: int
    status: str  # "SUCCESS" or "FAILURE"
    result: str

# --- GUI & Window Management Events ---

@dataclass
class DisplayFileInEditor:
    """Requests that the Code Viewer open or focus a tab for a specific file."""
    file_path: str
    file_content: str

@dataclass
class RefreshFileTree:
    """Requests that the Code Viewer's file tree re-scans the disk."""
    pass

@dataclass
class LogMessageReceived:
    """A standardized event for logging to the Log Viewer window."""
    source: str
    level: str  # e.g., "info", "error", "success"
    message: str

@dataclass
class BranchUpdated:
    """Published by the ProjectManager when the Git branch changes."""
    branch_name: str

@dataclass
class ProjectCreated:
    """Published by the ProjectManager when a new project is created and becomes active."""
    project_name: str
    project_path: str