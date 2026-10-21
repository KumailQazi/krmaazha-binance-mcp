FROM python:3.12-slim-bookworm

WORKDIR /app

# Install minimal build essentials for wheel compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project specification files
COPY pyproject.toml README.md ./

# Install package dependencies and ASGI production server
RUN pip install --no-cache-dir --upgrade pip hatchling uvicorn starlette
COPY src/ src/
RUN pip install --no-cache-dir .

# Copy application assets
COPY . .

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

EXPOSE 8000

# Start gateway server with healthcheck and SSE support
CMD ["python", "-m", "krmaazha_binance_mcp.gateway_server"]
