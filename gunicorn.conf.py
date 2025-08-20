# gunicorn.conf.py
import os

# Gunicorn config variables
# Use the WEB_CONCURRENCY env var if set, otherwise default to a sensible number.
workers = int(os.environ.get('WEB_CONCURRENCY', 4))
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