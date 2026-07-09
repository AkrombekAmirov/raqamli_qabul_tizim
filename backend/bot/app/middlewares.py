"""Middleware'lar - spam himoyasi (Redis asosida, ko'p instansga chidamli)."""
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from redis.asyncio import Redis

log = structlog.get_logger()


class ThrottlingMiddleware(BaseMiddleware):
    """Redis asosidagi throttling.

    Har bir foydalanuvchi uchun qisqa TTL li kalit qo'yiladi. Kalit mavjud
    bo'lsa (ya'ni juda tez bosildi) - so'rov e'tiborsiz qoldiriladi.
    Redis'da saqlangani uchun bot qayta ishga tushsa yoki bir necha instans
    ishlasa ham to'g'ri ishlaydi (10k+ yuklamaga mos).
    """

    def __init__(self, redis: Redis, rate_limit: float = 0.5) -> None:
        self.redis = redis
        # millisekundlarda TTL (Redis PX)
        self.ttl_ms = max(1, int(rate_limit * 1000))

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None:
            key = f"throttle:{user.id}"
            try:
                # NX + PX: faqat kalit yo'q bo'lsa qo'yadi, TTL bilan
                was_set = await self.redis.set(key, 1, px=self.ttl_ms, nx=True)
                if not was_set:
                    return None
            except Exception:
                # Redis vaqtincha ishlamasa, throttlingni o'tkazib yuboramiz
                # (bot ishlashda davom etsin, bloklanib qolmasin).
                log.warning("throttling_redis_unavailable")
        return await handler(event, data)
