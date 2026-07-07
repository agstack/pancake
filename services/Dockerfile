FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary

COPY pancake_services ./pancake_services
COPY specs ./specs

EXPOSE 8100

CMD ["uvicorn", "pancake_services.grants.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8100"]
