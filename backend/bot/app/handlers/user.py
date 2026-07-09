"""Murojaatchi (foydalanuvchi) uchun handlerlar - FSM oqimi."""
import structlog
from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.gemini_service import get_ai_response
from app.config import get_settings
from app.db.crud import (
    create_application,
    get_admin_by_region,
    get_application,
    get_or_create_user,
    update_application_message_info,
)
from app.db.models import ApplicationCategory, Region
from app.db.session import get_session
from app.keyboards import (
    CATEGORY_LABELS,
    REGION_LABELS,
    STATUS_LABELS,
    admin_action_keyboard,
    category_keyboard,
    confirm_keyboard,
    phone_keyboard,
    region_keyboard,
    remove_keyboard,
    skip_attachment_keyboard,
)
from app.notify import safe_send_message
from app.states import ApplicationForm

log = structlog.get_logger()
router = Router()
settings = get_settings()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Assalomu alaykum! \U0001F44B\n\n"
        "Bu <b>Direktor qabuli</b> boti. Bu yerda o'z murojaatingizni "
        "(shikoyat, taklif, ariza yoki savol) qoldirishingiz mumkin.\n\n"
        "Iltimos, <b>familiya, ism va sharifingizni</b> to'liq yozing:"
    )
    await state.set_state(ApplicationForm.full_name)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Amal bekor qilindi. Qayta boshlash uchun /start bosing.",
        reply_markup=remove_keyboard()
    )


@router.message(ApplicationForm.full_name, F.text)
async def process_full_name(message: Message, state: FSMContext) -> None:
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Iltimos, to'liq ism-familiyangizni kiriting.")
        return
    await state.update_data(full_name=full_name)
    await message.answer(
        "Rahmat! Endi telefon raqamingizni yuboring:",
        reply_markup=phone_keyboard(),
    )
    await state.set_state(ApplicationForm.phone)


@router.message(ApplicationForm.phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.contact.phone_number)
    await _ask_region(message, state)


@router.message(ApplicationForm.phone, F.text)
async def process_phone_text(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    # Oddiy telefon raqam validatsiyasi
    if len(phone) < 9:
        await message.answer("Iltimos, to'g'ri telefon raqam kiriting.")
        return
    await state.update_data(phone=phone)
    await _ask_region(message, state)


async def _ask_region(message: Message, state: FSMContext) -> None:
    """Viloyat tanlashni so'raydi."""
    await message.answer(
        "\U0001F4CD Viloyatingizni tanlang:",
        reply_markup=region_keyboard(),
    )
    await state.set_state(ApplicationForm.region)


@router.callback_query(ApplicationForm.region, F.data.startswith("region:"))
async def process_region(call: CallbackQuery, state: FSMContext) -> None:
    """Viloyat tanlandi."""
    region_value = call.data.split(":", 1)[1]
    region = Region(region_value)
    await state.update_data(region=region_value)
    
    await call.message.edit_text(
        f"Tanlandi: {REGION_LABELS[region]}\n\n"
        "Murojaat turini tanlang:",
        reply_markup=category_keyboard(),
    )
    await state.set_state(ApplicationForm.category)
    await call.answer()


@router.callback_query(ApplicationForm.category, F.data.startswith("cat:"))
async def process_category(call: CallbackQuery, state: FSMContext) -> None:
    category_value = call.data.split(":", 1)[1]
    await state.update_data(category=category_value)
    await call.message.edit_text(
        f"Tanlandi: {CATEGORY_LABELS[ApplicationCategory(category_value)]}\n\n"
        "Endi murojaatingiz <b>matnini</b> batafsil yozing:"
    )
    await state.set_state(ApplicationForm.message_text)
    await call.answer()


@router.message(ApplicationForm.message_text, F.text)
async def process_message_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Iltimos, murojaatingizni batafsilroq yozing.")
        return
    await state.update_data(message_text=text)
    await message.answer(
        "Agar dalil sifatida rasm yoki hujjat qo'shmoqchi bo'lsangiz, hozir yuboring.\n"
        "Aks holda quyidagi tugmani bosing:",
        reply_markup=skip_attachment_keyboard(),
    )
    await state.set_state(ApplicationForm.attachment)


@router.message(ApplicationForm.attachment, F.photo)
async def process_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(
        attachment_file_id=message.photo[-1].file_id, attachment_type="photo"
    )
    await _show_confirmation(message, state)


@router.message(ApplicationForm.attachment, F.document)
async def process_document(message: Message, state: FSMContext) -> None:
    await state.update_data(
        attachment_file_id=message.document.file_id, attachment_type="document"
    )
    await _show_confirmation(message, state)


@router.callback_query(ApplicationForm.attachment, F.data == "skip_attach")
async def skip_attachment(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(attachment_file_id=None, attachment_type=None)
    await call.message.delete()
    await _show_confirmation(call.message, state)
    await call.answer()


async def _show_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    category = ApplicationCategory(data["category"])
    region = Region(data["region"])
    attach = "\u2705 Bor" if data.get("attachment_file_id") else "\u2014 Yo'q"
    await message.answer(
        "<b>Murojaatingizni tekshiring:</b>\n\n"
        f"\U0001F464 F.I.SH: {data['full_name']}\n"
        f"\U0001F4F1 Tel: {data.get('phone', '-')}\n"
        f"\U0001F4CD Viloyat: {REGION_LABELS[region]}\n"
        f"\U0001F4C2 Turi: {CATEGORY_LABELS[category]}\n"
        f"\U0001F4CE Ilova: {attach}\n\n"
        f"\U0001F4AC Matn:\n{data['message_text']}",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(ApplicationForm.confirm)


@router.callback_query(ApplicationForm.confirm, F.data == "confirm:no")
async def confirm_no(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "Murojaat bekor qilindi. Qayta boshlash uchun /start bosing."
    )
    await call.answer()


@router.callback_query(ApplicationForm.confirm, F.data == "confirm:yes")
async def confirm_yes(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    user_tg = call.from_user
    category = ApplicationCategory(data["category"])
    region = Region(data["region"])
    
    # AI javob berish imkoniyatini tekshirish
    ai_response = None
    is_ai_handled = False
    
    # Faqat savol va taklif kategoriyalari uchun AI ishlatiladi
    if category in (ApplicationCategory.QUESTION, ApplicationCategory.SUGGESTION):
        ai_answer, needs_admin = await get_ai_response(
            data["message_text"], 
            category.value
        )
        if not needs_admin and ai_answer:
            ai_response = ai_answer
            is_ai_handled = True
    
    try:
        async with get_session() as session:
            # Viloyat adminini topish
            admin = await get_admin_by_region(session, region)
            assigned_admin_id = admin.id if admin else None
            
            user = await get_or_create_user(
                session,
                telegram_id=user_tg.id,
                full_name=data["full_name"],
                phone=data.get("phone"),
                region=region,
                language=data.get("language", "uz"),
            )
            application = await create_application(
                session,
                user=user,
                category=category,
                region=region,
                message_text=data["message_text"],
                attachment_file_id=data.get("attachment_file_id"),
                attachment_type=data.get("attachment_type"),
                assigned_admin_id=assigned_admin_id,
                ai_response=ai_response,
                is_ai_handled=is_ai_handled,
            )
            app_id = application.id
    except Exception:
        log.exception("application_save_failed", telegram_id=user_tg.id)
        await call.message.edit_text(
            "\u26A0 Kutilmagan xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring."
        )
        await call.answer()
        return

    # AI javob bergan bo'lsa
    if is_ai_handled and ai_response:
        await call.message.edit_text(
            f"\u2705 Murojaatingiz qabul qilindi!\n\n"
            f"Murojaat raqamingiz: <b>#{app_id}</b>\n\n"
            f"\U0001F916 <b>Avtomatik javob:</b>\n{ai_response}\n\n"
            f"<i>Agar bu javob sizga yordam bermagan bo'lsa, /start bosib qayta murojaat qiling.</i>"
        )
        await call.answer("Yuborildi!")
        # AI hal qilgan murojaatlar ham adminga xabar sifatida boradi (nazorat uchun)
        await _notify_admins(call, data, app_id, region, ai_response=ai_response)
    else:
        await call.message.edit_text(
            f"\u2705 Murojaatingiz qabul qilindi!\n\n"
            f"Murojaat raqamingiz: <b>#{app_id}</b>\n"
            f"Holatini bilish uchun: <code>/status {app_id}</code>\n\n"
            f"\U0001F4CD Viloyat: {REGION_LABELS[region]}\n"
            f"Murojaatingiz tegishli adminga yuborildi."
        )
        await call.answer("Yuborildi!")
        await _notify_admins(call, data, app_id, region)
    
    await state.clear()


async def _notify_admins(
    call: CallbackQuery, 
    data: dict, 
    app_id: int, 
    region: Region,
    ai_response: str | None = None
) -> None:
    """Viloyat adminiga yoki asosiy guruhga xabar yuboradi."""
    category = ApplicationCategory(data["category"])
    
    # AI javob bergan bo'lsa, boshqacha format
    if ai_response:
        caption = (
            f"\U0001F916 <b>AI javob berdi - Murojaat #{app_id}</b>\n\n"
            f"\U0001F4CD {REGION_LABELS[region]}\n"
            f"\U0001F464 {data['full_name']}\n"
            f"\U0001F4F1 {data.get('phone', '-')}\n"
            f"\U0001F4C2 {CATEGORY_LABELS[category]}\n\n"
            f"\U0001F4AC <b>Savol:</b>\n{data['message_text']}\n\n"
            f"\U0001F916 <b>AI javobi:</b>\n{ai_response}"
        )
        reply_markup = None  # AI hal qilgan uchun tugma kerak emas
    else:
        caption = (
            f"\U0001F514 <b>Yangi murojaat #{app_id}</b>\n\n"
            f"\U0001F4CD {REGION_LABELS[region]}\n"
            f"\U0001F464 {data['full_name']}\n"
            f"\U0001F4F1 {data.get('phone', '-')}\n"
            f"\U0001F4C2 {CATEGORY_LABELS[category]}\n\n"
            f"\U0001F4AC {data['message_text']}"
        )
        reply_markup = admin_action_keyboard(app_id)
    
    bot = call.bot
    
    # Viloyat adminini topish
    admin_chat_id = settings.admin_group_id  # Default: asosiy guruh
    async with get_session() as session:
        admin = await get_admin_by_region(session, region)
        if admin:
            admin_chat_id = admin.telegram_id
    
    sent = await safe_send_message(
        bot,
        admin_chat_id,
        caption,
        reply_markup=reply_markup,
    )
    
    if not sent:
        log.error("admin_notify_failed", application_id=app_id, region=region.value)
        # Fallback: asosiy guruhga yuborish
        if admin_chat_id != settings.admin_group_id:
            sent = await safe_send_message(
                bot,
                settings.admin_group_id,
                caption,
                reply_markup=reply_markup,
            )
    
    # Message ID ni saqlash (javob kuzatish uchun)
    if sent and not ai_response:
        try:
            async with get_session() as session:
                await update_application_message_info(
                    session, app_id, sent.message_id, admin_chat_id
                )
        except Exception:
            log.warning("message_info_save_failed", application_id=app_id)
    
    # Ilova yuborish
    if data.get("attachment_file_id") and not ai_response:
        try:
            if data["attachment_type"] == "photo":
                await bot.send_photo(
                    admin_chat_id, data["attachment_file_id"]
                )
            else:
                await bot.send_document(
                    admin_chat_id, data["attachment_file_id"]
                )
        except Exception:
            log.warning("admin_attachment_send_failed", application_id=app_id)


@router.message(Command("status"))
async def cmd_status(message: Message, command: CommandObject) -> None:
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Foydalanish: <code>/status &lt;raqam&gt;</code>")
        return
    app_id = int(command.args.strip())
    async with get_session() as session:
        application = await get_application(session, app_id)
        if application is None or application.user.telegram_id != message.from_user.id:
            await message.answer("Bunday raqamli murojaat topilmadi.")
            return
        
        region_label = REGION_LABELS.get(application.region, "Noma'lum")
        text = (
            f"Murojaat <b>#{application.id}</b>\n"
            f"\U0001F4CD Viloyat: {region_label}\n"
            f"Holati: {STATUS_LABELS.get(application.status)}\n"
        )
        
        if application.is_ai_handled and application.ai_response:
            text += f"\n\U0001F916 <b>AI javobi:</b>\n{application.ai_response}\n"
        
        if application.admin_reply:
            text += f"\n\u2709 <b>Admin javobi:</b>\n{application.admin_reply}"
        
        await message.answer(text)
