FROM mcr.microsoft.com/devcontainers/python:3.14-trixie

RUN apt-get update \
    && apt-get install -y --no-install-recommends gnupg jq zip \
    && curl -fsSL https://packages.stripe.dev/api/security/keypair/stripe-cli-gpg/public | gpg --dearmor -o /usr/share/keyrings/stripe.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/stripe.gpg] https://packages.stripe.dev/stripe-cli-debian-local stable main" > /etc/apt/sources.list.d/stripe.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends stripe \
    && rm -rf /var/lib/apt/lists/*

USER vscode
ENV PATH="/home/vscode/.local/bin:${PATH}"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
