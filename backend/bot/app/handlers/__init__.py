from aiogram import Router

from app.handlers import admin, user


def get_main_router() -> Router:
    router = Router()
    router.include_router(admin.router)
    router.include_router(user.router)
    return router
