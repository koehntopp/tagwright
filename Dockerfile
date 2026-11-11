FROM python:3.14-slim
ARG TARGETARCH
ARG DRCALC_VERSION=0.1.0
RUN apt-get update && apt-get install -y --no-install-recommends flac chromaprint-tools curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# drcalc (dynamic range): the release binary for this architecture, checked against the published SHA256SUMS (ADR 0036)
RUN set -e; \
    case "$TARGETARCH" in amd64) t=x86_64 ;; arm64) t=aarch64 ;; *) echo "unsupported arch $TARGETARCH" >&2; exit 1 ;; esac; \
    d="drcalc-v${DRCALC_VERSION}-${t}-unknown-linux-musl"; \
    base="https://github.com/koehntopp/drcalc/releases/download/v${DRCALC_VERSION}"; \
    curl -fsSL -o "/tmp/${d}.tar.gz" "${base}/${d}.tar.gz"; \
    curl -fsSL -o /tmp/SHA256SUMS "${base}/SHA256SUMS"; \
    (cd /tmp && grep " ${d}.tar.gz\$" SHA256SUMS | sha256sum -c -); \
    tar -xzf "/tmp/${d}.tar.gz" -C /tmp; \
    install -m 0755 "/tmp/${d}/drcalc" /usr/local/bin/drcalc; \
    rm -rf /tmp/drcalc-* /tmp/SHA256SUMS
# rsgain has no apt package: build it and drop the binary into ./bin
COPY bin/ /usr/local/bin/
WORKDIR /app
COPY app.py ./
COPY pipeline/ pipeline/
COPY static/ static/
ENV DATA_DIR=/data ROOT=/staging INGEST_DIR=/flac/ingest
EXPOSE 8080
CMD ["uv", "run", "app.py"]
