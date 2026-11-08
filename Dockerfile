FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends flac chromaprint-tools curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# rsgain and drmeter have no apt packages known to me: build them and drop the binaries into ./bin
COPY bin/ /usr/local/bin/
WORKDIR /app
COPY app.py index.html ./
COPY static/ static/
ENV DATA_DIR=/data ROOT=/staging INGEST_DIR=/flac/ingest DISCOGS_DIR=/opt/discogs
EXPOSE 8080
CMD ["uv", "run", "app.py"]
