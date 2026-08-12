# ---------- Etapa de construccion ----------
FROM python:3.13-slim AS constructor

WORKDIR /app

# Dependencias de compilacion, solo en esta etapa.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/instalacion -r requirements.txt


# ---------- Etapa final ----------
FROM python:3.13-slim

# Usuario sin privilegios con UID fijo.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --create-home app

# Solo las librerias ya compiladas, sin herramientas de construccion.
COPY --from=constructor /instalacion /usr/local

WORKDIR /app
COPY --chown=app:app . .

USER app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "app.principal:app", "--host", "0.0.0.0", "--port", "8000"]
