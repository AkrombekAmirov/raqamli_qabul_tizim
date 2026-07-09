"""Xabar yuborishning xavfsiz yordamchilari.

10k+ foydalanuvchida quyidagilar muhim:
- Telegram flood limiti (TelegramRetryAfter) -> kutib qayta yuborish
- Foydalanuvchi botni bloklagan (TelegramForbiddenError) -> jimgina yutish
- Boshqa xatolar -> log, lekin botni yiqitmaslik
"""
import asyncio

import structlog
from aiogram import Bot
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import Message

log = structlog.get_logger()


async def safe_send_message(
    bot: Bot, chat_id: int, text: str, max_retries: int = 3, **kwargs
) -> Message | None:
    """Xabarni xavfsiz yuboradi. Message qaytaradi yoki None."""
    for attempt in range(max_retries):
        try:
            return await bot.send_message(chat_id, text, **kwargs)
        except TelegramRetryAfter as e:
            log.warning("flood_control", retry_after=e.retry_after, chat_id=chat_id)
            await asyncio.sleep(e.retry_after + 1)
        except TelegramForbiddenError:
            log.info("user_blocked_bot", chat_id=chat_id)
            return None
        except Exception:
            log.exception("send_message_failed", chat_id=chat_id, attempt=attempt)
            return None
    return None
