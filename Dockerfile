# PullRaptor - Pinned Python 3.12 Deterministic Runtime
FROM python:3.12-slim

# Install git (required by snapshot and diff inspection kernel)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Configure environment: standard unbuffered output and deterministic pathing
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src:/app

WORKDIR /app

# Run as non-privileged user for boundary isolation
RUN useradd -m -u 1000 -s /bin/bash pullraptor

COPY pyproject.toml README.md /app/
COPY src/ /app/src/
COPY service/ /app/service/
COPY sdk/ /app/sdk/
RUN pip install --no-cache-dir /app

RUN chown -R pullraptor:pullraptor /app

USER pullraptor

# Default entrypoint exposes the customer CLI; run acceptance tests only in CI/dev profiles.
CMD ["pullraptor", "--help"]
