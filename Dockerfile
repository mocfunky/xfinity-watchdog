FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy

RUN apt-get update && \
    apt-get install -y curl ca-certificates gnupg && \
    curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash && \
    apt-get update && \
    apt-get install -y speedtest && \
    pip install --no-cache-dir requests playwright==1.52.0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app