# Minimal Dockerfile for Railway deployment of the FastAPI server_old
# It serves endpoints to upload/download SQLite and a public snapshot

FROM python:3.11-slim

# Install runtime deps
RUN pip install --no-cache-dir --upgrade pip

# Create app directory
WORKDIR /app

# Copy server_old files
COPY server-db/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY server /app

# Storage directory (may be ephemeral on Railway)
ENV STORAGE_DIR=/app/storage
RUN mkdir -p /app/storage

# Security: must override in Railway variables
ENV JWT_SECRET=change-me
# Example users list: "manager:password@default"
ENV USERS=manager:password@default

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
