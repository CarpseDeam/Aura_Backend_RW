# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# --- THE OPTIMIZATION MAGIC ---
# 1. Copy ONLY the requirements file first.
COPY requirements.txt .

# 2. Install the dependencies. This layer will be cached and only re-run
#    if requirements.txt changes. This is the biggest time-saver.
RUN pip install --no-cache-dir -r requirements.txt

# 3. Now, copy the rest of your application code.
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# --- THE FIX for Railway ---
# Railway provides the PORT environment variable. Gunicorn will bind to it.
# This command runs your application using the Gunicorn production server.
CMD ["gunicorn", "-c", "gunicorn.conf.py", "src.main:app"]