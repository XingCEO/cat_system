# Multi-stage Dockerfile for Zeabur Deployment

# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
# Build production assets
# Note: vite output dir is 'dist' by default
RUN npm run build

# Stage 2: Setup Backend & Serve
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy frontend assets from builder stage to 'static' folder
# main.py looks for 'static' folder in CWD or BASE_DIR
COPY --from=frontend-builder /app/dist /app/static

# Create logs directory
RUN mkdir -p logs

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port (Zeabur uses 8080 by default, but injects PORT env)
EXPOSE 8080

# Run application
# Use sh -c to expand environment variables
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
