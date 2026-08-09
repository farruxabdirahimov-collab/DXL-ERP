# --- 1-bosqich: Mini App'ni yig'amiz ---
FROM node:22-slim AS web

WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY web/ ./
RUN npm run build


# --- 2-bosqich: backend ---
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Tashkent

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini pytest.ini ./
COPY migrations/ ./migrations/
COPY app/ ./app/
COPY seed/ ./seed/

# Yig'ilgan Mini App'ni FastAPI static sifatida beradi
COPY --from=web /web/dist ./web/dist

EXPOSE 8000

# PORT platforma tomonidan berilishi mumkin; berilmasa 8000 ishlatiladi.
# DIQQAT: bu buyruqni `railway.json` dagi `startCommand` bilan almashtirmang —
# u yerda zaxira qiymat bo'lmasa, PORT bo'sh bo'lganda uvicorn ishga tushmaydi.
CMD ["sh", "-c", "echo \"DXL ERP ishga tushmoqda, port=${PORT:-8000}\" && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
