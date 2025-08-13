# --- Stage 1: The "Builder" - Our Messy Workshop ---
# We start with a full Python image to get all the build tools
FROM python:3.11-slim as builder

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies that some Python packages might need
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy ONLY the requirements file first to leverage Docker's caching
COPY requirements.txt .

# Install all our dependencies, including the giant sentence-transformers.
# This is where the big download happens.
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# --- Stage 2: The "Runner" - Our Pristine Clean Room ---
# We start with a fresh, tiny Python image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the pre-compiled packages from our "builder" workshop,
# leaving all the messy build caches and ML models behind.
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Now, copy our actual application code into the clean room
COPY . .

# Expose the port that our app will run on. Railway will use this.
EXPOSE 8000

# The command to start our app. Note we no longer need the --port flag
# because Railway will map its $PORT to the one we EXPOSE'd.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]