"""Reply va inline klaviaturalar."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import ApplicationCategory, ApplicationStatus, Region

CATEGORY_LABELS = {
    ApplicationCategory.COMPLAINT: "\U0001F534 Shikoyat",
    ApplicationCategory.SUGGESTION: "\U0001F4A1 Taklif",
    ApplicationCategory.REQUEST: "\U0001F4DD Ariza / iltimos",
    ApplicationCategory.QUESTION: "\u2753 Savol",
}

STATUS_LABELS = {
    ApplicationStatus.NEW: "\U0001F195 Yangi",
    ApplicationStatus.IN_PROGRESS: "\U0001F504 Ko'rib chiqilmoqda",
    ApplicationStatus.RESOLVED: "\u2705 Hal qilindi",
    ApplicationStatus.REJECTED: "\u274C Rad etilgan",
}

REGION_LABELS = {
    Region.TOSHKENT_SHAHAR: "\U0001F3D9 Toshkent shahri",
    Region.TOSHKENT_VILOYAT: "\U0001F33E Toshkent viloyati",
    Region.ANDIJON: "\U0001F3D4 Andijon",
    Region.NAMANGAN: "\U0001F338 Namangan",
    Region.FARGONA: "\U0001F347 Farg'ona",
    Region.SIRDARYO: "\U0001F30A Sirdaryo",
    Region.JIZZAX: "\U0001F3DC Jizzax",
    Region.SAMARQAND: "\U0001F3DB Samarqand",
    Region.NAVOIY: "\U0001F3ED Navoiy",
    Region.BUXORO: "\U0001F54C Buxoro",
    Region.QASHQADARYO: "\U0001F304 Qashqadaryo",
    Region.SURXONDARYO: "\u2600 Surxondaryo",
    Region.XORAZM: "\U0001F3F0 Xorazm",
    Region.QORAQALPOGISTON: "\U0001F3DD Qoraqalpog'iston",
}


def remove_keyboard() -> ReplyKeyboardRemove:
    """Reply klaviaturani olib tashlash."""
    return ReplyKeyboardRemove()


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="\U0001F4F1 Telefon raqamni yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def region_keyboard() -> InlineKeyboardMarkup:
    """14 ta viloyat tanlash klaviaturasi."""
    builder = InlineKeyboardBuilder()
    for region, label in REGION_LABELS.items():
        builder.button(text=label, callback_data=f"region:{region.value}")
    builder.adjust(2)  # 2 ta ustun
    return builder.as_markup()


def category_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category, label in CATEGORY_LABELS.items():
        builder.button(text=label, callback_data=f"cat:{category.value}")
    builder.adjust(1)
    return builder.as_markup()


def skip_attachment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\u23ED Fayl qo'shmasdan davom etish", callback_data="skip_attach")]
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="\u2705 Yuborish", callback_data="confirm:yes"),
                InlineKeyboardButton(text="\u274C Bekor qilish", callback_data="confirm:no"),
            ]
        ]
    )


def admin_action_keyboard(
    application_id: int, status: ApplicationStatus = ApplicationStatus.NEW
) -> InlineKeyboardMarkup | None:
    """Admin tugmalari. Hal qilingan/rad etilgan murojaatlar uchun
    tugmalar ko'rsatilmaydi (None) - keraksiz qayta bosishning oldini oladi."""
    if status in (ApplicationStatus.RESOLVED, ApplicationStatus.REJECTED):
        return None
    rows = []
    if status != ApplicationStatus.IN_PROGRESS:
        rows.append(
            [
                InlineKeyboardButton(
                    text="\U0001F504 Ko'rib chiqilmoqda",
                    callback_data=f"adm:progress:{application_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="\u2709 Javob berish",
                callback_data=f"adm:reply:{application_id}",
            ),
            InlineKeyboardButton(
                text="\u2705 Hal qilindi",
                callback_data=f"adm:resolved:{application_id}",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def filter_category_keyboard() -> InlineKeyboardMarkup:
    """/list uchun kategoriya bo'yicha filtr tugmalari."""
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001F4CB Barchasi", callback_data="flt:cat:all")
    for category, label in CATEGORY_LABELS.items():
        builder.button(text=label, callback_data=f"flt:cat:{category.value}")
    builder.adjust(1)
    return builder.as_markup()


def filter_status_keyboard(category: str) -> InlineKeyboardMarkup:
    """Kategoriya tanlangach, holat bo'yicha qo'shimcha filtr."""
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001F4CB Barcha holatlar", callback_data=f"flt:st:{category}:all")
    for status, label in STATUS_LABELS.items():
        builder.button(text=label, callback_data=f"flt:st:{category}:{status.value}")
    builder.adjust(1)
    return builder.as_markup()


def filter_region_keyboard() -> InlineKeyboardMarkup:
    """Viloyat bo'yicha filtr."""
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001F4CB Barcha viloyatlar", callback_data="flt:reg:all")
    for region, label in REGION_LABELS.items():
        builder.button(text=label, callback_data=f"flt:reg:{region.value}")
    builder.adjust(2)
    return builder.as_markup()


def admin_region_keyboard() -> InlineKeyboardMarkup:
    """Admin qo'shishda viloyat tanlash."""
    builder = InlineKeyboardBuilder()
    for region, label in REGION_LABELS.items():
        builder.button(text=label, callback_data=f"adm_reg:{region.value}")
    builder.adjust(2)
    return builder.as_markup()
