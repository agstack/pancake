# Generic builder for the AR2 node (agstack/ar2) used by the demo stack.
# Best-effort fallback so the demo works without modifying that repo.
# Build context is the ar2 checkout.
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . /app
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi \
    && pip install --no-cache-dir "uvicorn[standard]" fastapi

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
