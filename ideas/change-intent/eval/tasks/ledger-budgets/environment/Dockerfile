# Workspace for the ledger-budgets task. The agent (Copilot CLI + SDK) is installed by the Harbor
# agent class at run time; this image only needs Python, git, pytest for the agent's own test runs,
# and uv/uvx for the Reward Kit verifier.
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl bash ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pytest==8.4.1

WORKDIR /app
COPY seed/ /app/
RUN git init -q && git -c user.name=seed -c user.email=seed@example.invalid add -A \
    && git -c user.name=seed -c user.email=seed@example.invalid commit -q -m "seed"
