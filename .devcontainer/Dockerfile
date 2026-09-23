FROM mcr.microsoft.com/devcontainers/python:3.14-trixie

RUN apt-get update \
    && apt-get install -y --no-install-recommends jq zip \
    && rm -rf /var/lib/apt/lists/*

USER vscode
ENV PATH="/home/vscode/.local/bin:${PATH}"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
