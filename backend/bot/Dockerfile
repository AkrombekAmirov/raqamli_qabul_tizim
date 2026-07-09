FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Tashkent

WORKDIR /app

# Tizim bog'liqliklari (asyncpg build uchun zarur bo'lishi mumkin)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY entrypoint.sh ./entrypoint.sh
# CRLF (Windows) qator tugatgichlarini olib tashlaymiz va bajariladigan qilamiz.
# Bu "no such file or directory" xatosining oldini oladi.
RUN sed -i 's/\r$//' ./entrypoint.sh \
    && chmod +x ./entrypoint.sh

# Xavfsizlik uchun root emas, alohida foydalanuvchi
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

# /bin/sh orqali chaqiramiz - bu ham CRLF muammosiga chidamli.
ENTRYPOINT ["/bin/sh", "./entrypoint.sh"]
