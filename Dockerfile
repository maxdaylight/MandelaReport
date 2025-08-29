## Builder: install dependencies into a venv
FROM python:3.12.6-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Keep builder patched (does not affect final image layers)
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated virtual environment for app deps
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache/pip

COPY ./src ./src
COPY ./templates ./templates
COPY ./static ./static
RUN mkdir -p /app/data

## Runtime: minimal, nonroot, distroless image to minimize CVEs
FROM gcr.io/distroless/python3-debian12:nonroot AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only what we need from the builder
COPY --from=builder --chown=nonroot:nonroot /opt/venv /opt/venv
COPY --from=builder --chown=nonroot:nonroot /app/src /app/src
COPY --from=builder --chown=nonroot:nonroot /app/templates /app/templates
COPY --from=builder --chown=nonroot:nonroot /app/static /app/static
COPY --from=builder --chown=nonroot:nonroot /app/data /app/data

EXPOSE 8081

# Use the venv's Python to ensure site-packages are on sys.path
ENTRYPOINT ["/opt/venv/bin/python", "-m", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8081"]
