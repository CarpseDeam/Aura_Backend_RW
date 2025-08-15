# llm_server/gunicorn.conf.py
import os

# Gunicorn config variables
workers = int(os.environ.get('GUNICORN_PROCESSES', '4'))
threads = int(os.environ.get('GUNICORN_THREADS', '1'))
worker_class = 'uvicorn.workers.UvicornWorker'

# Bind to 0.0.0.0 and the port specified by the PORT env var.
# Google Cloud Run provides the PORT environment variable.
port = os.environ.get('PORT', '8080')
bind = f"0.0.0.0:{port}"

# Logging
# Redirect stdout/stderr to specified file paths
loglevel = 'info'
accesslog = '-'  # to stdout
errorlog = '-'   # to stderr

# Add current directory to pythonpath to help with module resolution.
# This is the key fix for the ModuleNotFoundError.
pythonpath = '.'