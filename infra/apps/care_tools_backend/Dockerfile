# Mock clinical tools backend (synthetic data only). Built in ACR by Terraform (`az acr build`).
FROM python:3.12-slim

# Pinned uv binary for fast, reproducible installs from pyproject.toml.
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv

WORKDIR /srv
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

COPY app ./app

# Run as an unprivileged user.
RUN useradd --uid 10001 --no-create-home appuser
USER 10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
