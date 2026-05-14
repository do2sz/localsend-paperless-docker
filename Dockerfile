# syntax=docker/dockerfile:1.7

# ---- Build localsend-cli (Go) ----
FROM golang:1.23-alpine AS lsbuild
RUN apk add --no-cache git
ARG LOCALSEND_CLI_REPO=https://github.com/0w0mewo/localsend-cli
ARG LOCALSEND_CLI_REF=v0.0.6
RUN git clone --depth 1 --branch ${LOCALSEND_CLI_REF} ${LOCALSEND_CLI_REPO} /src
WORKDIR /src
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/localsend-cli .

# ---- Final image ----
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends tini ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=lsbuild /out/localsend-cli /usr/local/bin/localsend-cli

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY forwarder/ ./forwarder/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN useradd -u 1000 -m -d /home/app app \
 && mkdir -p /data/incoming /data/retry \
 && chown -R app:app /data /app

USER app
WORKDIR /data

EXPOSE 53317/tcp 53317/udp

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
