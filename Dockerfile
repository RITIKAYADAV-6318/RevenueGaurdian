# ==============================================================================
# Revenue Guardian - Dockerfile
# ==============================================================================
# Use an official, lightweight Python runtime as a parent image
FROM python:3.11-slim

# Set system environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for building certain Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Create directories for SQLite DB and reports, ensuring write permissions
RUN mkdir -p /app/docs/reports && chmod -R 777 /app

# Expose ports:
# - 8000: FastAPI Backend / MCP Server
# - 8501: Streamlit Dashboard
EXPOSE 8000 8501

# The actual command is overridden in docker-compose.yml
CMD ["python"]
