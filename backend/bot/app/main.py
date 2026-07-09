"""Bot kirish nuqtasi. Polling rejimi, graceful shutdown bilan.

Eslatma: jadvallar Alembic migratsiyalari orqali yaratiladi
(entrypoint.sh ichida `alembic upgrade head`). Shu sababli bu yerda
create_all chaqirilmaydi - faqat DB ulanishi tayyorligini kutamiz.
"""
import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import ErrorEvent
from redis.asyncio import Redis

from app.ai_service import check_ollama_health
from app.config import get_settings
from app.db.session import engine, wait_for_db
from app.handlers import get_main_router
from app.logging_config import setup_logging
from app.middlewares import ThrottlingMiddleware

log = structlog.get_logger()


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info("bot_starting")

    # DB ulanishi tayyorligini tekshiradi (retry ichida).
    await wait_for_db()
    
    # Ollama AI serverini tekshirish
    if settings.ai_enabled:
        ai_ok = await check_ollama_health()
        if ai_ok:
            log.info("ollama_ai_enabled", model=settings.ollama_model)
        else:
            log.warning("ollama_ai_unavailable", 
                       url=settings.ollama_url,
                       model=settings.ollama_model)

    redis = Redis(host=settings.redis_host, port=settings.redis_port, db=0)
    storage = RedisStorage(redis=redis)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)

    dp.update.middleware(ThrottlingMiddleware(redis=redis, rate_limit=0.5))
    dp.include_router(get_main_router())

    @dp.error()
    async def global_error_handler(event: ErrorEvent) -> bool:
        log.exception("unhandled_update_error", exception=str(event.exception))
        try:
            if event.update.message:
                await event.update.message.answer(
                    "\u26A0 Kutilmagan xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."
                )
            elif event.update.callback_query:
                await event.update.callback_query.answer(
                    "Xatolik yuz berdi, qayta urinib ko'ring.", show_alert=True
                )
        except Exception:
            pass
        return True

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        log.info("bot_polling_started")
        await dp.start_polling(bot)
    finally:
        log.info("bot_shutting_down")
        await bot.session.close()
        await storage.close()
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("bot_stopped")
