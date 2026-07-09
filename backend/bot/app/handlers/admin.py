"""Admin (direktor / kotib) uchun handlerlar."""
import contextlib

import structlog
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.db.crud import (
    count_applications,
    create_admin,
    get_admin_by_telegram_id,
    get_application,
    get_applications_by_admin,
    get_stats,
    list_admins,
    list_applications,
    update_admin,
    update_application_status,
)
from app.db.models import ApplicationCategory, ApplicationStatus, Region
from app.db.session import get_session
from app.keyboards import (
    CATEGORY_LABELS,
    REGION_LABELS,
    STATUS_LABELS,
    admin_action_keyboard,
    admin_region_keyboard,
    filter_category_keyboard,
    filter_region_keyboard,
    filter_status_keyboard,
)
from app.states import AdminManagement, AdminReply

log = structlog.get_logger()
router = Router()
settings = get_settings()


def _is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin yoki super admin ekanligini tekshiradi."""
    return user_id in settings.admin_id_list


def _is_super_admin(user_id: int) -> bool:
    """Foydalanuvchi super admin (birinchi admin) ekanligini tekshiradi."""
    return settings.admin_id_list and user_id == settings.admin_id_list[0]


def _application_caption(app, status_label: str) -> str:
    """Guruhdagi murojaat xabari matni (holat bilan)."""
    region_label = REGION_LABELS.get(app.region, "Noma'lum")
    
    # Javob berilgan bo'lsa, boshqacha format
    if app.status == ApplicationStatus.RESOLVED and app.admin_reply:
        return (
            f"\u2705 <b>Murojaat #{app.id} - JAVOB BERILDI</b>\n\n"
            f"\U0001F4CD {region_label}\n"
            f"\U0001F464 {app.user.full_name}\n"
            f"\U0001F4F1 {app.user.phone or '-'}\n"
            f"\U0001F4C2 {CATEGORY_LABELS[app.category]}\n\n"
            f"\U0001F4AC <b>Savol:</b>\n{app.message_text[:200]}{'...' if len(app.message_text) > 200 else ''}\n\n"
            f"\U0001F4DD <b>Javob:</b>\n{app.admin_reply}"
        )
    
    return (
        f"\U0001F514 <b>Murojaat #{app.id}</b>\n\n"
        f"\U0001F4CD {region_label}\n"
        f"\U0001F464 {app.user.full_name}\n"
        f"\U0001F4F1 {app.user.phone or '-'}\n"
        f"\U0001F4C2 {CATEGORY_LABELS[app.category]}\n"
        f"\U0001F4CA Holat: <b>{status_label}</b>\n\n"
        f"\U0001F4AC {app.message_text}"
    )


# ---------------------------------------------------------------------------
# Statistika
# ---------------------------------------------------------------------------
@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    
    # Viloyat admini bo'lsa, faqat o'z viloyati statistikasi
    region_filter = None
    async with get_session() as session:
        admin = await get_admin_by_telegram_id(session, message.from_user.id)
        if admin:
            region_filter = admin.region
        
        stats = await get_stats(session, region=region_filter)
    
    region_text = f" ({REGION_LABELS.get(region_filter, '')})" if region_filter else ""
    await message.answer(
        f"\U0001F4CA <b>Statistika{region_text}</b>\n\n"
        f"Jami: {stats['total']}\n"
        f"\U0001F195 Yangi: {stats['new']}\n"
        f"\U0001F504 Ko'rib chiqilmoqda: {stats['in_progress']}\n"
        f"\u2705 Hal qilindi: {stats['resolved']}\n"
        f"\u274C Rad etilgan: {stats['rejected']}"
    )


# ---------------------------------------------------------------------------
# /myapps - Adminga tayinlangan murojaatlar
# ---------------------------------------------------------------------------
@router.message(Command("myapps"))
async def cmd_my_applications(message: Message) -> None:
    """Adminga tayinlangan murojaatlar."""
    async with get_session() as session:
        admin = await get_admin_by_telegram_id(session, message.from_user.id)
        if not admin:
            await message.answer("Siz viloyat admini sifatida ro'yxatdan o'tmagansiz.")
            return
        
        # Yangi va ko'rib chiqilayotgan murojaatlar
        new_apps = await get_applications_by_admin(
            session, message.from_user.id, ApplicationStatus.NEW, limit=5
        )
        in_progress_apps = await get_applications_by_admin(
            session, message.from_user.id, ApplicationStatus.IN_PROGRESS, limit=5
        )
    
    region_label = REGION_LABELS.get(admin.region, "Noma'lum")
    lines = [f"\U0001F4CB <b>Sizning murojaatlaringiz</b>\n{region_label}\n"]
    
    if new_apps:
        lines.append("\n\U0001F195 <b>Yangi:</b>")
        for app in new_apps:
            lines.append(
                f"  <b>#{app.id}</b> {CATEGORY_LABELS[app.category]}\n"
                f"    {app.message_text[:50]}..."
            )
    
    if in_progress_apps:
        lines.append("\n\U0001F504 <b>Ko'rib chiqilmoqda:</b>")
        for app in in_progress_apps:
            lines.append(
                f"  <b>#{app.id}</b> {CATEGORY_LABELS[app.category]}\n"
                f"    {app.message_text[:50]}..."
            )
    
    if not new_apps and not in_progress_apps:
        lines.append("\nHozircha ochiq murojaatlar yo'q.")
    
    await message.answer("\n".join(lines))


# ---------------------------------------------------------------------------
# /list - kategoriya va holat bo'yicha filtrlash
# ---------------------------------------------------------------------------
@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer(
        "\U0001F5C2 Murojaatlarni qaysi <b>tur</b> bo'yicha ko'rmoqchisiz?",
        reply_markup=filter_category_keyboard(),
    )


@router.callback_query(F.data.startswith("flt:cat:"))
async def filter_pick_category(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    category = call.data.split(":")[2]
    await call.message.edit_text(
        "\U0001F4CA Endi <b>holat</b> bo'yicha filtrlang:",
        reply_markup=filter_status_keyboard(category),
    )
    await call.answer()


@router.callback_query(F.data.startswith("flt:st:"))
async def filter_show_results(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    _, _, category_raw, status_raw = call.data.split(":")
    category = None if category_raw == "all" else ApplicationCategory(category_raw)
    status = None if status_raw == "all" else ApplicationStatus(status_raw)
    
    # Viloyat admini bo'lsa, faqat o'z viloyati
    region_filter = None
    async with get_session() as session:
        admin = await get_admin_by_telegram_id(session, call.from_user.id)
        if admin:
            region_filter = admin.region
        
        total = await count_applications(
            session, category=category, status=status, region=region_filter
        )
        items = await list_applications(
            session, category=category, status=status, region=region_filter, limit=10
        )

    if not items:
        await call.message.edit_text("Ushbu filtr bo'yicha murojaat topilmadi.")
        await call.answer()
        return

    lines = [f"\U0001F4CB <b>Topildi: {total} ta</b> (oxirgi {len(items)}):\n"]
    for app in items:
        region_label = REGION_LABELS.get(app.region, "?")[:2]  # Qisqa
        reply_status = "\u2709" if app.admin_reply else "\u23F3"
        lines.append(
            f"{reply_status} <b>#{app.id}</b> {region_label} {CATEGORY_LABELS[app.category]} - "
            f"{STATUS_LABELS[app.status]}\n"
            f"   \U0001F464 {app.user.full_name} | \U0001F4F1 {app.user.phone or '-'}\n"
            f"   \U0001F4AC {app.message_text[:60]}"
            + ("..." if len(app.message_text) > 60 else "")
        )
    await call.message.edit_text("\n".join(lines))
    await call.answer()


# ---------------------------------------------------------------------------
# Holatni o'zgartirish (idempotent - qayta bosishga chidamli)
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:progress:"))
async def admin_set_progress(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    app_id = int(call.data.split(":")[2])
    await _change_status(call, app_id, ApplicationStatus.IN_PROGRESS)


@router.callback_query(F.data.startswith("adm:resolved:"))
async def admin_set_resolved(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    app_id = int(call.data.split(":")[2])
    await _change_status(call, app_id, ApplicationStatus.RESOLVED)


async def _change_status(
    call: CallbackQuery, app_id: int, status: ApplicationStatus
) -> None:
    label = STATUS_LABELS[status]
    async with get_session() as session:
        application, changed = await update_application_status(
            session, app_id, status
        )
        if application is None:
            await call.answer("Murojaat topilmadi", show_alert=True)
            return
        user_tg_id = application.user.telegram_id
        new_caption = _application_caption(application, label)
        new_kb = admin_action_keyboard(app_id, status)

    if not changed:
        await call.answer("Bu holat allaqachon o'rnatilgan.", show_alert=False)
        return

    with contextlib.suppress(TelegramBadRequest):
        await call.message.edit_text(new_caption, reply_markup=new_kb)

    await call.answer(f"Holat: {label}")

    with contextlib.suppress(Exception):
        await call.bot.send_message(
            user_tg_id,
            f"\u2139 Murojaatingiz #{app_id} holati o'zgardi: <b>{label}</b>",
        )


# ---------------------------------------------------------------------------
# Javob berish
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:reply:"))
async def admin_start_reply(call: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    app_id = int(call.data.split(":")[2])
    await state.update_data(reply_app_id=app_id, reply_message_id=call.message.message_id)
    await state.set_state(AdminReply.waiting_reply_text)
    await call.message.answer(f"#{app_id} murojaatga javob matnini yuboring:")
    await call.answer()


@router.message(AdminReply.waiting_reply_text, F.text)
async def admin_send_reply(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    app_id = data.get("reply_app_id")
    original_message_id = data.get("reply_message_id")
    reply_text = message.text.strip()
    
    async with get_session() as session:
        application, _ = await update_application_status(
            session, app_id, ApplicationStatus.RESOLVED, admin_reply=reply_text
        )
        if application is None:
            await message.answer("Murojaat topilmadi.")
            await state.clear()
            return
        user_tg_id = application.user.telegram_id
        admin_chat_id = application.admin_chat_id
        admin_message_id = application.admin_message_id
    
    # Foydalanuvchiga javob yuborish
    try:
        await message.bot.send_message(
            user_tg_id,
            f"\u2709 Murojaatingiz #{app_id} bo'yicha javob:\n\n{reply_text}",
        )
        await message.answer("\u2705 Javob yuborildi va murojaat hal qilindi.")
    except Exception:
        log.warning("reply_delivery_failed", application_id=app_id)
        await message.answer(
            "\u26A0 Javob saqlandi, lekin foydalanuvchiga yetkazilmadi "
            "(u botni bloklagan bo'lishi mumkin)."
        )
    
    # Asl xabarni yangilash (javob berildi deb ko'rsatish)
    if admin_message_id and admin_chat_id:
        try:
            async with get_session() as session:
                app = await get_application(session, app_id)
                if app:
                    new_caption = _application_caption(app, STATUS_LABELS[ApplicationStatus.RESOLVED])
                    await message.bot.edit_message_text(
                        new_caption,
                        chat_id=admin_chat_id,
                        message_id=admin_message_id,
                        reply_markup=None,  # Tugmalarni olib tashlash
                    )
        except Exception:
            log.warning("original_message_update_failed", application_id=app_id)
    
    await state.clear()


# ---------------------------------------------------------------------------
# Admin boshqaruvi (faqat super admin uchun)
# ---------------------------------------------------------------------------
@router.message(Command("admins"))
async def cmd_list_admins(message: Message) -> None:
    """Barcha viloyat adminlari ro'yxati."""
    if not _is_super_admin(message.from_user.id):
        await message.answer("Bu buyruq faqat bosh admin uchun.")
        return
    
    async with get_session() as session:
        admins = await list_admins(session, active_only=False)
    
    if not admins:
        await message.answer(
            "Hozircha viloyat adminlari yo'q.\n\n"
            "Yangi admin qo'shish: /addadmin"
        )
        return
    
    lines = ["\U0001F465 <b>Viloyat adminlari:</b>\n"]
    for admin in admins:
        status = "\u2705" if admin.is_active else "\u274C"
        region_label = REGION_LABELS.get(admin.region, "Noma'lum")
        lines.append(
            f"{status} <b>{admin.full_name}</b>\n"
            f"   ID: <code>{admin.telegram_id}</code>\n"
            f"   {region_label}"
        )
    
    lines.append("\n\nYangi admin qo'shish: /addadmin")
    await message.answer("\n".join(lines))


@router.message(Command("addadmin"))
async def cmd_add_admin(message: Message, state: FSMContext) -> None:
    """Yangi viloyat admini qo'shish."""
    if not _is_super_admin(message.from_user.id):
        await message.answer("Bu buyruq faqat bosh admin uchun.")
        return
    
    await message.answer(
        "Yangi admin qo'shish.\n\n"
        "Admin bo'ladigan foydalanuvchining <b>Telegram ID</b> sini yuboring:\n\n"
        "<i>ID ni bilish uchun foydalanuvchi @userinfobot ga /start yozishi mumkin.</i>"
    )
    await state.set_state(AdminManagement.waiting_admin_id)


@router.message(AdminManagement.waiting_admin_id, F.text)
async def process_admin_id(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("Iltimos, faqat raqam (Telegram ID) yuboring.")
        return
    
    telegram_id = int(message.text.strip())
    
    # Mavjud adminmi tekshirish
    async with get_session() as session:
        existing = await get_admin_by_telegram_id(session, telegram_id)
        if existing:
            await message.answer(
                f"Bu foydalanuvchi allaqachon admin: {existing.full_name}\n"
                f"Viloyat: {REGION_LABELS.get(existing.region, 'Noma\'lum')}"
            )
            await state.clear()
            return
    
    await state.update_data(new_admin_telegram_id=telegram_id)
    await message.answer("Adminning <b>to'liq ismini</b> yuboring:")
    await state.set_state(AdminManagement.waiting_admin_name)


@router.message(AdminManagement.waiting_admin_name, F.text)
async def process_admin_name(message: Message, state: FSMContext) -> None:
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Iltimos, to'liq ism kiriting.")
        return
    
    await state.update_data(new_admin_name=full_name)
    await message.answer(
        f"Admin: <b>{full_name}</b>\n\n"
        "Endi <b>viloyatni</b> tanlang:",
        reply_markup=admin_region_keyboard(),
    )
    await state.set_state(AdminManagement.waiting_admin_region)


@router.callback_query(AdminManagement.waiting_admin_region, F.data.startswith("adm_reg:"))
async def process_admin_region(call: CallbackQuery, state: FSMContext) -> None:
    region_value = call.data.split(":")[1]
    region = Region(region_value)
    data = await state.get_data()
    
    async with get_session() as session:
        admin = await create_admin(
            session,
            telegram_id=data["new_admin_telegram_id"],
            full_name=data["new_admin_name"],
            region=region,
        )
    
    await call.message.edit_text(
        f"\u2705 Yangi admin qo'shildi!\n\n"
        f"\U0001F464 {admin.full_name}\n"
        f"ID: <code>{admin.telegram_id}</code>\n"
        f"\U0001F4CD {REGION_LABELS[region]}\n\n"
        f"Endi bu foydalanuvchi {REGION_LABELS[region]} murojaatlarini ko'ra oladi."
    )
    await call.answer("Admin qo'shildi!")
    await state.clear()
