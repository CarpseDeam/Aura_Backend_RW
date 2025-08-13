# src/foundry/actions/file_system_actions.py
"""
Contains actions related to direct file system manipulation.
All functions in this module assume that any relative paths have been
resolved to absolute paths by the ExecutorService before being passed in.
"""
import logging
import shutil
import asyncio
from pathlib import Path
from src.event_bus import EventBus
from src.events import StreamCodeChunk
from src.core.managers import ProjectManager

logger = logging.getLogger(__name__)


async def write_file(path: str, content: str, event_bus: EventBus, project_manager: ProjectManager) -> str:
    """
    Writes content to a specified file, creating directories if necessary.
    This version first streams the content to the GUI before writing.
    """
    try:
        # --- CRITICAL VALIDATION ---
        if not content or not content.strip():
            error_message = f"Error: Attempted to write an empty or whitespace-only file to '{path}'. Operation aborted."
            logger.warning(error_message)
            return error_message

        logger.info(f"Attempting to stream and write to file: {path}")
        path_obj = Path(path)

        # Determine the relative path for the event
        relative_path = path
        if project_manager.active_project_path and path_obj.is_absolute():
            try:
                relative_path = str(path_obj.relative_to(project_manager.active_project_path))
            except ValueError:
                pass  # Path is not within the project, use the full path as a fallback

        # --- Streaming Logic ---
        # Clear the tab first by sending an empty chunk with a special flag/initial call
        event_bus.emit("stream_code_chunk", StreamCodeChunk(filename=relative_path, chunk="", is_first_chunk=True))
        await asyncio.sleep(0.01)

        chunk_size = 100
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            event_bus.emit("stream_code_chunk", StreamCodeChunk(filename=relative_path, chunk=chunk))
            await asyncio.sleep(0.01)

        # --- File Write Logic ---
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        bytes_written = path_obj.write_text(content, encoding='utf-8')
        success_message = f"Successfully wrote {bytes_written} bytes to {path}"
        logger.info(success_message)
        return success_message
    except Exception as e:
        error_message = f"An unexpected error occurred while writing to file {path}: {e}"
        logger.exception(error_message)
        return error_message


def append_to_file(path: str, content: str) -> str:
    """Appends content to the end of a specified file."""
    try:
        logger.info(f"Attempting to append to file: {path}")
        path_obj = Path(path)
        if not path_obj.is_file():
            return f"Error: File not found at path '{path}'. Cannot append."

        with path_obj.open('a', encoding='utf-8') as f:
            if path_obj.read_text(encoding='utf-8') and not path_obj.read_text(encoding='utf-8').endswith('\n'):
                f.write('\n')
            bytes_written = f.write(content)

        success_message = f"Successfully appended {bytes_written} bytes to {path}"
        logger.info(success_message)
        return success_message
    except Exception as e:
        error_message = f"An unexpected error occurred while appending to file {path}: {e}"
        logger.exception(error_message)
        return error_message


def read_file(path: str) -> str:
    """Reads the content of a specified file."""
    try:
        logger.info(f"Attempting to read file: {path}")
        path_obj = Path(path)
        if not path_obj.exists():
            return f"Error: File not found at path '{path}'"
        if not path_obj.is_file():
            return f"Error: Path '{path}' is a directory, not a file."
        content = path_obj.read_text(encoding='utf-8')
        logger.info(f"Successfully read {len(content)} characters from {path}")
        return content
    except Exception as e:
        error_message = f"An unexpected error occurred while reading file {path}: {e}"
        logger.exception(error_message)
        return error_message


def list_files(path: str = ".") -> str:
    """Lists files and directories at a given path."""
    try:
        if not path:
            path = "."
        logger.info(f"Listing contents of directory: {path}")
        path_obj = Path(path)
        if not path_obj.exists():
            return f"Error: Directory not found at path '{path}'"
        if not path_obj.is_dir():
            return f"Error: Path '{path}' is a file, not a directory."
        entries = [f"{entry.name}/" if entry.is_dir() else entry.name for entry in sorted(path_obj.iterdir())]
        if not entries:
            return f"Directory '{path}' is empty."
        result = f"Contents of '{path}':\n" + "\n".join(entries)
        logger.info(f"Successfully listed {len(entries)} items in {path}")
        return result
    except Exception as e:
        error_message = f"An unexpected error occurred while listing directory {path}: {e}"
        logger.exception(error_message)
        return error_message


def create_directory(path: str) -> str:
    """Creates a new, empty directory."""
    try:
        logger.info(f"Attempting to create directory: {path}")
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=False)
        success_message = f"Successfully created directory at {path}"
        logger.info(success_message)
        return success_message
    except FileExistsError:
        error_message = f"Error: Directory already exists at {path}"
        logger.warning(error_message)
        return error_message
    except Exception as e:
        error_message = f"An unexpected error occurred while creating directory {path}: {e}"
        logger.exception(error_message)
        return error_message


def create_package_init(path: str) -> str:
    """
    Initializes a directory as a Python package by creating an __init__.py file.
    """
    try:
        dir_path = Path(path)
        logger.info(f"Attempting to initialize package at: {dir_path}")

        dir_path.mkdir(parents=True, exist_ok=True)

        init_file_path = dir_path / "__init__.py"

        if init_file_path.exists():
            message = f"Package already initialized at '{path}'."
            logger.warning(message)
            return message

        package_name = dir_path.name
        content = f'"""Initializes the \'{package_name}\' package."""\n'

        init_file_path.write_text(content, encoding='utf-8')

        success_message = f"Successfully initialized package '{package_name}' at '{path}'."
        logger.info(success_message)
        return success_message

    except Exception as e:
        error_message = f"An unexpected error occurred while initializing package at {path}: {e}"
        logger.exception(error_message)
        return error_message


def delete_directory(path: str) -> str:
    """
    Recursively deletes a directory and all its contents.
    """
    try:
        logger.info(f"Attempting to recursively delete directory: {path}")
        path_obj = Path(path)

        if not path_obj.exists():
            error_message = f"Error: Cannot delete. Directory not found at '{path}'."
            logger.warning(error_message)
            return error_message
        if not path_obj.is_dir():
            error_message = f"Error: Path '{path}' is a file, not a directory. Use 'delete_file' instead."
            logger.warning(error_message)
            return error_message

        shutil.rmtree(path_obj)
        success_message = f"Successfully deleted directory: {path}"
        logger.info(success_message)
        return success_message
    except Exception as e:
        error_message = f"An unexpected error occurred while deleting directory {path}: {e}"
        logger.exception(error_message)
        return error_message


def copy_file(source_path: str, destination_path: str) -> str:
    """
    Copies a file from a source to a destination, preserving metadata.
    Creates parent directories for the destination if they don't exist.
    """
    try:
        source = Path(source_path)
        destination = Path(destination_path)
        logger.info(f"Attempting to copy '{source}' to '{destination}'.")

        if not source.exists():
            error_message = f"Error: Source file not found at '{source_path}'."
            logger.warning(error_message)
            return error_message
        if not source.is_file():
            error_message = f"Error: Source path '{source_path}' is a directory, not a file. This tool only copies files."
            logger.warning(error_message)
            return error_message

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(destination))

        success_message = f"Successfully copied file from '{source_path}' to '{destination_path}'."
        logger.info(success_message)
        return success_message
    except Exception as e:
        error_message = f"An unexpected error occurred while copying file: {e}"
        logger.exception(error_message)
        return error_message


def move_file(source_path: str, destination_path: str) -> str:
    """
    Moves a file from a source to a destination. Can be used to rename files.
    """
    try:
        source = Path(source_path)
        destination = Path(destination_path)
        logger.info(f"Attempting to move '{source}' to '{destination}'.")

        if not source.exists():
            error_message = f"Error: Source file not found at '{source_path}'."
            logger.warning(error_message)
            return error_message
        if not source.is_file():
            error_message = f"Error: Source path '{source_path}' is a directory, not a file. This tool only moves files."
            logger.warning(error_message)
            return error_message

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

        success_message = f"Successfully moved file from '{source_path}' to '{destination_path}'."
        logger.info(success_message)
        return success_message
    except Exception as e:
        error_message = f"An unexpected error occurred while moving file: {e}"
        logger.exception(error_message)
        return error_message


def delete_file(path: str) -> str:
    """
    Deletes a single file after performing safety checks.
    """
    try:
        logger.info(f"Attempting to delete file: {path}")
        path_obj = Path(path)

        if not path_obj.exists():
            error_message = f"Error: Cannot delete. File not found at '{path}'."
            logger.warning(error_message)
            return error_message

        if not path_obj.is_file():
            error_message = f"Error: Path '{path}' is a directory, not a file. This tool only deletes files."
            logger.warning(error_message)
            return error_message

        path_obj.unlink()
        success_message = f"Successfully deleted file: {path}"
        logger.info(success_message)
        return success_message
    except Exception as e:
        error_message = f"An unexpected error occurred while deleting file {path}: {e}"
        logger.exception(error_message)
        return error_message