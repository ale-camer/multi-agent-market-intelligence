# Multi-Agent Market Intelligence platform Dockerfile
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Create dedicated non-root user and group
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

# Copy project specification and application source
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install application package and production dependencies
RUN pip install --upgrade pip && \
    pip install .

# Set ownership of application files to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose standard application port
EXPOSE 8000

# Container healthcheck using standard Python HTTP probe against /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Launch ASGI application server
CMD ["uvicorn", "multi_agent_market_intelligence.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
