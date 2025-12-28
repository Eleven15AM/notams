# Stage 1: Base image with dependencies
FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Development/Test image
FROM base AS test

COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt

COPY src/ /app/src/
COPY tests/ /app/tests/

CMD ["pytest", "-v", "tests/"]

# Stage 3: Production application image
FROM base AS app

# Copy only application code
COPY src/ /app/src/
COPY queries/ /app/queries/

# Create directory for database
RUN mkdir -p /app/data

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command - can be overridden
CMD ["python", "-m", "src.main"]