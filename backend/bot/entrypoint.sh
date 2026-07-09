#!/bin/sh
# Bot ishga tushishdan oldin migratsiyalarni qo'llaydi.
# DB tayyor bo'lguncha kutish asosiy retry mantiq (tenacity) va compose
# healthcheck bilan ta'minlangan.
set -e

echo "[entrypoint] Migratsiyalar qo'llanmoqda..."
alembic upgrade head

echo "[entrypoint] Bot ishga tushmoqda..."
exec python -m app.main
