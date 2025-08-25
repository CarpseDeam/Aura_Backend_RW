# Dockerfile
# Use an official lightweight Python image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy ONLY the requirements files first to leverage Docker's layer caching.
# This is the most critical step for speeding up deployments.
# If these files don't change, the `pip install` step will be skipped.
COPY requirements.txt ./
COPY llm_server/requirements.txt ./llm_server_requirements.txt

# Install all dependencies for both the main app and the LLM server
RUN pip install --no-cache-dir -r requirements.txt


# Now, copy the rest of your application code
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# The command to run your main application. Gunicorn will look for gunicorn.conf.py.
# Note: The gunicorn.conf.py needs to be adjusted to point to the correct app.
# We will create a specific one for the main app.
CMD ["gunicorn", "-c", "gunicorn_main.conf.py", "src.main:app"]