# syntax=docker/dockerfile:1
# Base image pinned by digest (python:3.12-slim-bookworm, resolved 2026-09-23). Update deliberately.
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

FROM ${PYTHON_IMAGE} AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-dev --no-install-project --extra postgres --extra s3
COPY src ./src
COPY skills ./skills
RUN uv sync --locked --no-dev --no-editable --extra postgres --extra s3

FROM ${PYTHON_IMAGE}
RUN useradd --create-home --uid 10001 rsf \n    && mkdir -p /home/rsf/blobs && chown rsf:rsf /home/rsf/blobs  # volume mount point owned by the app user
WORKDIR /app
COPY --from=build --chown=rsf:rsf /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 RSF_ENVIRONMENT=production
USER rsf
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["rsf", "serve", "--host", "0.0.0.0", "--port", "8000"]
