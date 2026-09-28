# FALLBACK A2A adapter (only built when a2a_mode = "adapter").
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv

WORKDIR /srv
COPY pyproject.toml ./
# Explicit pre-release pins in pyproject.toml are allowed by uv's default pre-release strategy.
RUN uv pip install --system --no-cache -r pyproject.toml

COPY app.py ./

RUN useradd --uid 10001 --no-create-home appuser
USER 10001

ENV PORT=8080
EXPOSE 8080
CMD ["python", "app.py"]
