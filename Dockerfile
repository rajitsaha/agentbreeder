FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first (needed for pyproject.toml build)
COPY pyproject.toml README.md ./
COPY api/ api/
COPY cli/ cli/
COPY engine/ engine/
COPY registry/ registry/
COPY connectors/ connectors/
COPY sdk/ sdk/
COPY alembic/ alembic/
COPY alembic.ini ./

# Install Python dependencies
RUN pip install --no-cache-dir .

# Run as non-root user
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8000

# Run API server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
