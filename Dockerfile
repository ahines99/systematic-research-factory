# syntax=docker/dockerfile:1
# Base image pinned by digest (Python 3.14.7, resolved 2026-09-27). Update deliberately.
ARG PYTHON_IMAGE=python:3.14-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56

FROM ${PYTHON_IMAGE} AS base
# The upstream digest predates Debian's OpenSSL security update; patch both build and runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade \
        libssl3=3.0.22-1~deb12u1 openssl=3.0.22-1~deb12u1 \
    && rm -rf /var/lib/apt/lists/*

FROM base AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.18@sha256:3adc3706091ce7c2fe595e669628caedd6d951551b92b258b7e7dbe06d9440bc /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-dev --no-install-project --extra postgres --extra s3
COPY src ./src
COPY skills ./skills
COPY evals/golden ./evals/golden
RUN uv sync --locked --no-dev --no-editable --extra postgres --extra s3

FROM base
RUN useradd --create-home --uid 10001 rsf \
    && mkdir -p /home/rsf/blobs && chown rsf:rsf /home/rsf/blobs  # volume mount point owned by the app user
WORKDIR /app
COPY --from=build --chown=rsf:rsf /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 RSF_ENVIRONMENT=production
USER rsf
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["rsf", "serve", "--host", "0.0.0.0", "--port", "8000"]
