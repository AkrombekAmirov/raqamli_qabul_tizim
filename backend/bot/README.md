# Direktor qabuli - Telegram bot

aiogram 3 + PostgreSQL (TimescaleDB) + Redis (FSM) asosidagi murojaat qabul qiluvchi bot.

## Imkoniyatlar

- Murojaatchi ro'yxatdan o'tadi (F.I.SH, telefon) va murojaat yuboradi (shikoyat / taklif / ariza / savol)
- Rasm yoki hujjat ilova qilish
- Yakuniy tasdiqlash va unikal murojaat raqami (`#ID`)
- `/status <ID>` bilan holatni tekshirish
- Admin guruhiga avtomatik bildirishnoma
- Admin: holatni o'zgartirish, javob berish, `/stats`

## Ishga tushirish (local, Docker)

1. `.env` faylini tayyorlang:

   ```bash
   cp backend/bot/.env.example backend/bot/.env
   ```

   `BOT_TOKEN`, `ADMIN_GROUP_ID`, `ADMIN_IDS` ni to'ldiring.
   DB va Redis qiymatlari asosiy compose fayl bilan bir xil bo'lsin.

2. Ishga tushiring (loyiha ildizidan, bitta buyruq):

   ```bash
   docker compose up --build
   ```

## Ma'lumotlar bazasi migratsiyalari (Alembic)

Jadvallar bot ishga tushganda **avtomatik** yaratiladi: konteyner `entrypoint.sh`
ichida `alembic upgrade head` bajaradi. Qo'lda hech narsa qilish shart emas.

Modellarni o'zgartirgach yangi migratsiya yaratish:

```bash
docker compose run --rm bot alembic revision --autogenerate -m "ozgarish tavsifi"
```

Migratsiyalarni qo'lda qo'llash / orqaga qaytarish:

```bash
# eng so'nggi holatga
docker compose run --rm bot alembic upgrade head
# bir qadam orqaga
docker compose run --rm bot alembic downgrade -1
```

## Muhim eslatmalar (ehtimoliy muammolar oldi olingan)

- **DB tayyorligi**: bot `wait_for_db` da retry qiladi, `depends_on ... service_healthy` bilan kutadi.
- **Migratsiyalar**: `entrypoint.sh` botdan oldin `alembic upgrade head` bajaradi (create_all ishlatilmaydi, ziddiyat yo'q).
- **Uzilgan DB ulanishi**: `pool_pre_ping` va `pool_recycle` yoqilgan.
- **Spam**: `ThrottlingMiddleware` har foydalanuvchi bosishini cheklaydi.
- **FSM barqarorligi**: holatlar Redis'da saqlanadi (qayta ishga tushganda yo'qolmaydi).
- **Xavfsizlik**: konteyner root emas; token faqat `.env` da.
- **Graceful shutdown**: `finally` blokida bot, redis, engine yopiladi.
- **DB_HOST**: bot compose ichki tarmoq orqali `db` xostiga ulanadi (port 5432, tashqi 5436 emas).
