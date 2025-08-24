####Dockerfile

# 1. Start with an official Python base image that includes Playwright's dependencies.
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# 2. Set the working directory inside the container.
WORKDIR /app

# 3. Copy the requirements file and install Python dependencies first.
# This is a best practice that leverages Docker's caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. This is the crucial step! We install ONLY the chromium browser and its
# necessary system-level dependencies. This keeps the image smaller.
RUN playwright install --with-deps chromium

# 5. Copy the rest of your application code into the container.
COPY . .

# 6. Tell Docker what port the application will run on. Railway will use this.
EXPOSE 8000

# 7. The command to run your application. This new format uses a shell
# to correctly expand the ${PORT} environment variable.
CMD ["/bin/sh", "-c", "gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT}"]