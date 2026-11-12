# ── Stage 1: build rsgain (no package for it) ────────────────────────────────
FROM python:3.14-slim AS rsgain
ARG RSGAIN_VERSION=3.7
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates xz-utils cmake make g++ pkg-config \
        libavcodec-dev libavformat-dev libavutil-dev libswresample-dev \
        libebur128-dev libinih-dev libfmt-dev libutfcpp-dev libtag1-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL "https://github.com/complexlogic/rsgain/releases/download/v${RSGAIN_VERSION}/rsgain-${RSGAIN_VERSION}-source.tar.xz" \
        | tar -xJ -C /tmp \
    && cmake -S /tmp/rsgain-${RSGAIN_VERSION} -B /tmp/rsgain-build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /tmp/rsgain-build --parallel \
    && strip /tmp/rsgain-build/rsgain
# The runtime packages rsgain links against, so the final stage installs exactly those.
RUN ldd /tmp/rsgain-build/rsgain | awk '/=>/ {print $3}' | xargs -r realpath | xargs -r dpkg -S 2>/dev/null \
        | cut -d: -f1 | sort -u > /tmp/rsgain-runtime-pkgs \
    && test -s /tmp/rsgain-runtime-pkgs

# ── Stage 2: runtime image ───────────────────────────────────────────────────
FROM python:3.14-slim
ARG TARGETARCH
ARG DRCALC_VERSION=0.1.0
COPY --from=rsgain /tmp/rsgain-runtime-pkgs /tmp/rsgain-runtime-pkgs
# fpcalc (chromaprint) and the libraries of rsgain
RUN apt-get update && apt-get install -y --no-install-recommends \
        libchromaprint-tools curl ca-certificates $(cat /tmp/rsgain-runtime-pkgs) \
    && rm -rf /var/lib/apt/lists/* /tmp/rsgain-runtime-pkgs
COPY --from=rsgain /tmp/rsgain-build/rsgain /usr/local/bin/rsgain
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
# The Python dependencies of app.py (its PEP 723 header is the one list), installed once at build time
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY app.py ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --script app.py --no-hashes -o /tmp/requirements.txt \
    && uv pip install --system -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt
COPY pipeline/ pipeline/
COPY library/ library/
COPY static/ static/
# The image's own data mount point; the two media folders come from compose (ADR 0055)
ENV DATA_DIR=/data
EXPOSE 8080
CMD ["python", "app.py"]
