# PullRaptor - Pinned Python 3.12 Deterministic Runtime
FROM python:3.12-slim

# Install git (required by snapshot and diff inspection kernel)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Configure environment: standard unbuffered output and deterministic pathing
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Run as non-privileged user for boundary isolation
RUN useradd -m -u 1000 -s /bin/bash pullraptor

COPY --chown=pullraptor:pullraptor src/ /app/src/
COPY --chown=pullraptor:pullraptor tests/ /app/tests/

USER pullraptor

# Allow git inspection on mounted workspace repositories regardless of host uid
RUN git config --global --add safe.directory '*'

# Default entrypoint runs the test suite
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
