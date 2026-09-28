# PRESENTER-ONLY: container image for the Care Coordination Agent (Foundry hosted agent or Container Apps).
# Build from workshop/:   docker build -f deploy/Dockerfile -t care-coordination-agent:1 .
# Training use only. Synthetic data. Not a medical device.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/app

WORKDIR /app
COPY deploy/requirements.txt deploy/requirements.txt
RUN pip install --no-cache-dir -r deploy/requirements.txt

# Only the runtime code: the agent package and the version registry (instructions lineage).
COPY src/ src/
COPY agent_versions/ agent_versions/
COPY deploy/app.py deploy/app.py

# Non-root user
RUN useradd --create-home --uid 10001 agent && chown -R agent /app
USER agent

EXPOSE 8088
CMD ["python", "deploy/app.py"]
