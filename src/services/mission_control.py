# src/services/mission_control.py
from typing import Dict
import asyncio

# This dictionary will store the active status for each user's mission.
# The key is the user_id (as a string), and the value is a boolean.
# True = Running, False = Stop Requested
_mission_states: Dict[str, bool] = {}
_lock = asyncio.Lock()


async def set_mission_running(user_id: str):
    """Marks a mission as running for a user."""
    async with _lock:
        _mission_states[user_id] = True


async def request_mission_stop(user_id: str):
    """Requests a graceful stop for a user's active mission."""
    async with _lock:
        if user_id in _mission_states:
            _mission_states[user_id] = False


async def is_mission_running(user_id: str) -> bool:
    """Checks if a mission should continue running for a user."""
    async with _lock:
        return _mission_states.get(user_id, True)


async def set_mission_finished(user_id: str):
    """Cleans up the state for a user's mission once it has fully stopped."""
    async with _lock:
        if user_id in _mission_states:
            del _mission_states[user_id]