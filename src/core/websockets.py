from typing import Dict
from fastapi import WebSocket, WebSocketException, status
import asyncio

class WebSocketManager:
    """
    Manages active WebSocket connections for a multi-user, multi-window environment.
    """

    def __init__(self):
        """
        Initializes the manager.
        The structure is: {user_id: {client_id: WebSocket}}
        This allows sending messages to all of a user's windows or to a specific one.
        """
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, client_id: str):
        """
        Accepts and stores a new WebSocket connection, associating it with a user
        and a unique client ID (for multi-window support).
        """
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}

        # Disconnect any existing client with the same ID for this user
        if client_id in self.active_connections[user_id]:
            # Raise a normal closure exception to the old connection
            old_socket = self.active_connections[user_id][client_id]
            await old_socket.close(code=status.WS_1001_GOING_AWAY, reason="New connection established")

        self.active_connections[user_id][client_id] = websocket
        print(f"✅ WebSocket connected: User '{user_id}', Client '{client_id}'")

    def disconnect(self, user_id: str, client_id: str):
        """
        Removes a WebSocket connection from the manager.
        """
        if user_id in self.active_connections and client_id in self.active_connections[user_id]:
            del self.active_connections[user_id][client_id]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            print(f"🔌 WebSocket disconnected: User '{user_id}', Client '{client_id}'")

    async def send_to_client(self, message: dict, user_id: str, client_id: str):
        """
        Sends a JSON message to a single, specific client window for a user.
        """
        if user_id in self.active_connections and client_id in self.active_connections[user_id]:
            websocket = self.active_connections[user_id][client_id]
            try:
                await websocket.send_json(message)
            except WebSocketException as e:
                print(f"Error sending to {user_id}/{client_id}: {e}. Disconnecting.")
                self.disconnect(user_id, client_id)

    async def broadcast_to_user(self, message: dict, user_id: str):
        """
        Sends a JSON message to ALL client windows for a specific user.
        """
        if user_id in self.active_connections:
            # Create a list of tasks to send messages concurrently
            tasks = [
                self.send_to_client(message, user_id, client_id)
                for client_id in self.active_connections[user_id]
            ]
            await asyncio.gather(*tasks)


# Create a single, globally accessible instance of the manager.
# This singleton will be shared across the entire application.
websocket_manager = WebSocketManager()