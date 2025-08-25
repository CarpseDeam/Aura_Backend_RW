# gunicorn_main.conf.py
import os

# Gunicorn config variables
workers = int(os.environ.get('GUNICORN_WORKERS', '3'))
worker_class = 'uvicorn.workers.UvicornWorker'

# Bind to the port specified by the PORT env var.
# Google Cloud Run and Railway provide the PORT environment variable.
port = os.environ.get('PORT', '8080')

# Bind to [::] to listen on all available IPv4 and IPv6 interfaces.
# This is essential for Railway's private networking.
bind = f"[::]:{port}"

# Logging
loglevel = 'info'
accesslog = '-'  # to stdout
errorlog = '-'   # to stderr