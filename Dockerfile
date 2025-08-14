# Dockerfile for the llm-server microservice

# Use an official Python runtime as a parent image.
FROM python:3.11-slim

# Set the working directory in the container to /app.
WORKDIR /app

# Set the PYTHONPATH environment variable.
# This ensures that Python can find modules in the /app directory,
# which is crucial for the `from src.providers` import.
ENV PYTHONPATH=/app

# --- Build & Dependency Installation ---

# Copy the requirements file first. This leverages Docker's layer caching.
# If requirements.txt doesn't change, this layer won't be rebuilt.
COPY llm_server/requirements.txt .

# Install the Python dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# --- Application Code ---

# Copy the microservice's main application file into the root of the WORKDIR.
COPY llm_server/main.py .

# Copy the shared 'providers' source code and its package initializer.
COPY src/providers/ /app/src/providers/
COPY src/__init__.py /app/src/__init__.py

# --- Network & Execution ---

# Expose port 8080 to allow communication with the service.
EXPOSE 8080

# Define the command to run the application using uvicorn.
# It will run the 'app' instance from the 'main.py' file which is now in /app.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]