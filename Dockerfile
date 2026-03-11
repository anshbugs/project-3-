FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GROWW_DATA_DIR=/app/data

WORKDIR /app

# Install runtime dependencies from the package definition.
COPY pyproject.toml ./pyproject.toml
RUN pip install --upgrade pip && pip install .

# Copy application code.
COPY groww_pulse ./groww_pulse
COPY run_scheduler.py ./run_scheduler.py

# Ensure data directories exist inside the container (used for logs, notes, etc.).
RUN mkdir -p /app/data

EXPOSE 8000

# Railway provides PORT; default to 8000 for local runs.
CMD ["sh", "-c", "uvicorn groww_pulse.api:app --host 0.0.0.0 --port ${PORT:-8000}"]

