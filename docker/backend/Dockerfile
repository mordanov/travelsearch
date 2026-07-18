FROM python:3.13-slim

WORKDIR /app

# Install system deps for Playwright and asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy application source
COPY backend/ .

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
