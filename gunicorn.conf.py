# gunicorn.conf.py
import os

# Gunicorn config variables
# --- THE FIX: Force a single worker process ---
# In a multi-worker environment, the in-memory WebSocketManager singleton is not shared,
# causing background tasks (like plan execution) to lose track of the user's WebSocket
# connection, which is handled by a different worker. Forcing a single worker ensures
# that all operations occur in the same process, making the in-memory manager reliable.
workers = 1
worker_class = 'uvicorn.workers.UvicornWorker'

# Bind to the port specified by the PORT env var.
# Google Cloud Run and Railway provide the PORT environment variable.
port = os.environ.get('PORT', '8080')

# --- THE CRITICAL FIX ---
# Bind to [::] to listen on all available IPv4 and IPv6 interfaces.
# This is essential for Railway's private networking.
bind = f"[::]:{port}"

# Logging
loglevel = 'info'
accesslog = '-'  # to stdout
errorlog = '-'   # to stderr

# --- THE FIX for ModuleNotFoundError ---
# Add the current directory to the Python path. This ensures that Gunicorn
# can find the 'src' module when the application starts.
pythonpath = '.'