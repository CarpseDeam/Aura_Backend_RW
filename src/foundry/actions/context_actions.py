# foundry/actions/context_actions.py
"""
Contains actions related to managing and indexing project context.
"""
import logging
import ast
from src.services.vector_context_service import VectorContextService
from src.core.managers.project_context import ProjectContext

logger = logging.getLogger(__name__)


def index_project_context(project_context: ProjectContext, vector_context_service: VectorContextService, path: str = ".") -> str:
    """
    Scans a directory for Python files, extracts functions and classes,
    and adds them to the vector database. This action is now sandboxed
    to the active project directory.

    Args:
        project_context: Injected by the ToolRunner. Contains the active project's root path.
        vector_context_service: Injected by the ToolRunner. The service for RAG.
        path: The path to scan, relative to the project root. Defaults to the root.

    Returns:
        A summary of the indexing operation.
    """
    if not project_context or not project_context.project_root:
        return "Error: Cannot index context. No active project."

    project_root = project_context.project_root
    scan_path = (project_root / path).resolve()

    # --- CRUCIAL SAFETY CHECK ---
    # Ensure the path to be scanned is safely within the active project's root directory.
    # This prevents contaminating the RAG database with the application's own source code.
    try:
        scan_path.relative_to(project_root)
    except ValueError:
        error_msg = f"Error: Indexing is only allowed within the active project. The path '{scan_path}' is outside of '{project_root}'."
        logger.error(error_msg)
        return error_msg

    if not scan_path.is_dir():
        return f"Error: The specified path '{scan_path}' is not a valid directory."

    logger.info(f"Starting project indexing from path: {scan_path}")
    documents = []
    metadatas = []

    # Exclude common virtual environment and metadata folders
    exclude_dirs = {'venv', '.venv', '__pycache__', 'node_modules', '.git', 'chroma_db'}

    py_files = [p for p in scan_path.rglob("*.py") if not any(excluded in p.parts for excluded in exclude_dirs)]

    for file_path in py_files:
        logger.debug(f"Processing file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    source_code = ast.unparse(node)
                    node_type = "function" if isinstance(node, ast.FunctionDef) else "class"

                    documents.append(source_code)
                    metadatas.append({
                        "file_path": str(file_path.relative_to(project_root)),
                        "node_type": node_type,
                        "node_name": node.name,
                    })
        except Exception as e:
            logger.warning(f"Could not parse or read file {file_path}: {e}")
            continue

    if not documents:
        return "No new functions or classes found to index in the specified path."

    vector_context_service.add_documents(documents, metadatas)

    return f"Successfully indexed {len(documents)} new code chunks (functions/classes) from {len(py_files)} Python files."