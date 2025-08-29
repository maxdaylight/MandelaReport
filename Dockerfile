## Builder: install dependencies into a portable target directory (no venv)
# Use the slim tag to pick up upstream security fixes; for production pin to a
# specific digest after scanning (e.g. python:3.12-slim@sha256:...)
FROM python:3.12-slim AS builder

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

# Install dependencies into a portable folder that can be copied into distroless
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --target=/app/lib -r requirements.txt \
    && rm -rf /root/.cache/pip

COPY ./src ./src
COPY ./templates ./templates
COPY ./static ./static
RUN mkdir -p /app/data

## Runtime: minimal, nonroot, distroless image to minimize CVEs
FROM gcr.io/distroless/python3-debian12:nonroot AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/lib

WORKDIR /app

# Copy only what we need from the builder. We copy the portable library folder
# rather than a virtualenv so the runtime can use the system /usr/bin/python3
COPY --from=builder --chown=nonroot:nonroot /app/lib /app/lib
COPY --from=builder --chown=nonroot:nonroot /app/src /app/src
COPY --from=builder --chown=nonroot:nonroot /app/templates /app/templates
COPY --from=builder --chown=nonroot:nonroot /app/static /app/static
COPY --from=builder --chown=nonroot:nonroot /app/data /app/data

EXPOSE 8081

# Run the distroless system Python and let PYTHONPATH point to our installed libs.
# Use the system python executable rather than a venv binary which won't exist.
ENTRYPOINT ["/usr/bin/python3", "-m", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8081"]
