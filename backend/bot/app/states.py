"""FSM holatlari - murojaat topshirish oqimi."""
from aiogram.fsm.state import State, StatesGroup


class ApplicationForm(StatesGroup):
    """Foydalanuvchi murojaat topshirish oqimi."""
    language = State()
    full_name = State()
    phone = State()
    region = State()        # Viloyat tanlash
    category = State()
    message_text = State()
    attachment = State()
    confirm = State()


class AdminReply(StatesGroup):
    """Admin javob berish oqimi."""
    waiting_reply_text = State()


class AdminManagement(StatesGroup):
    """Super admin - viloyat adminlarini boshqarish."""
    waiting_admin_id = State()
    waiting_admin_name = State()
    waiting_admin_region = State()
