# Thames Water Monitoring Service (external ingestion; no browser runtime)
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
ENV PATH="/usr/local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock* ./
COPY README.md ./

# Create the environment without installing the not-yet-copied local project.
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY src/ ./src/
COPY static/ ./static/
COPY scripts/ ./scripts/

RUN uv sync --frozen --no-dev

# Create data and logs directories
RUN mkdir -p /app/data /app/logs && \
    chmod 755 /app/data /app/logs

# Environment configuration
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/app/data/thames_water.db
ENV LOG_LEVEL=info
ENV PORT=8096
ENV SCRAPER_MODE=external

# Create non-root user for running the app
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8096

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8096/health || exit 1

# Run the application using the virtual environment directly
CMD ["/app/.venv/bin/uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8096"]
