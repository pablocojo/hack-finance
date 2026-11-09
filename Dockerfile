# Backend en un contenedor (Railway, Fly.io o cualquier servicio con Docker).
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt
COPY backend ./backend
COPY demo ./demo
# Las métricas que lee /jurado (GET /metricas/{nombre}).
COPY evals/resultados ./evals/resultados
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
