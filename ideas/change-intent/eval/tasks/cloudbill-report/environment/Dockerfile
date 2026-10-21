# Workspace for the cloudbill-report task (greenfield). The agent (Copilot CLI + SDK) is installed by the Harbor
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
# Warm the verifier's uvx cache so grading needs no network inside the 900 s verifier window.
RUN uvx --from 'harbor-rewardkit==0.2.3' rewardkit --help > /dev/null

RUN git config --system user.name eval && git config --system user.email eval@example.invalid \
    && git init -q && git add -A && git commit -q -m "seed"
