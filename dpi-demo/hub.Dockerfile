# Generic builder for the AR2 hub (agstack/ar2-hub) used by the demo stack.
# The hub repo may ship its own Dockerfile; this is a best-effort fallback so the
# demo works without modifying that repo. Build context is the ar2-hub checkout.
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . /app
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi \
    && pip install --no-cache-dir "uvicorn[standard]" fastapi

EXPOSE 8000
CMD ["uvicorn", "hub_main:app", "--host", "0.0.0.0", "--port", "8000"]
