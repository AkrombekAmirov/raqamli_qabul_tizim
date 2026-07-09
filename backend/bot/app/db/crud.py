"""Ma'lumotlar bazasi bilan ishlash funksiyalari."""
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Admin,
    Application,
    ApplicationCategory,
    ApplicationStatus,
    Region,
    User,
)


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    phone: str | None,
    region: Region | None,
    language: str,
) -> User:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone,
            region=region,
            language=language,
        )
        session.add(user)
        await session.flush()
    else:
        user.full_name = full_name
        if phone:
            user.phone = phone
        if region:
            user.region = region
        user.language = language
    return user


async def create_application(
    session: AsyncSession,
    user: User,
    category: ApplicationCategory,
    region: Region,
    message_text: str,
    attachment_file_id: str | None,
    attachment_type: str | None,
    assigned_admin_id: int | None = None,
    ai_response: str | None = None,
    is_ai_handled: bool = False,
) -> Application:
    application = Application(
        user=user,
        category=category,
        region=region,
        message_text=message_text,
        attachment_file_id=attachment_file_id,
        attachment_type=attachment_type,
        assigned_admin_id=assigned_admin_id,
        ai_response=ai_response,
        is_ai_handled=is_ai_handled,
    )
    session.add(application)
    await session.flush()
    return application


async def get_application(
    session: AsyncSession, application_id: int
) -> Application | None:
    result = await session.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.user),
            selectinload(Application.assigned_admin)
        )
    )
    return result.scalar_one_or_none()


async def update_application_status(
    session: AsyncSession,
    application_id: int,
    status: ApplicationStatus,
    admin_reply: str | None = None,
) -> tuple[Application | None, bool]:
    """Holatni yangilaydi.

    Qaytaradi: (application, changed) - changed=False bo'lsa holat allaqachon
    shu qiymatda edi (idempotent - foydalanuvchiga qayta xabar yubormaslik uchun).
    """
    application = await get_application(session, application_id)
    if application is None:
        return None, False
    changed = application.status != status or (
        admin_reply is not None and application.admin_reply != admin_reply
    )
    application.status = status
    if admin_reply is not None:
        application.admin_reply = admin_reply
    return application, changed


async def update_application_message_info(
    session: AsyncSession,
    application_id: int,
    admin_message_id: int,
    admin_chat_id: int,
) -> None:
    """Admin chatdagi xabar ID sini saqlaydi."""
    await session.execute(
        update(Application)
        .where(Application.id == application_id)
        .values(admin_message_id=admin_message_id, admin_chat_id=admin_chat_id)
    )


async def list_applications(
    session: AsyncSession,
    category: ApplicationCategory | None = None,
    status: ApplicationStatus | None = None,
    region: Region | None = None,
    limit: int = 10,
    offset: int = 0,
) -> list[Application]:
    """Filtrlangan murojaatlar ro'yxati (eng yangilari birinchi)."""
    stmt = select(Application).options(
        selectinload(Application.user),
        selectinload(Application.assigned_admin)
    )
    if category is not None:
        stmt = stmt.where(Application.category == category)
    if status is not None:
        stmt = stmt.where(Application.status == status)
    if region is not None:
        stmt = stmt.where(Application.region == region)
    stmt = stmt.order_by(Application.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_applications(
    session: AsyncSession,
    category: ApplicationCategory | None = None,
    status: ApplicationStatus | None = None,
    region: Region | None = None,
) -> int:
    stmt = select(func.count()).select_from(Application)
    if category is not None:
        stmt = stmt.where(Application.category == category)
    if status is not None:
        stmt = stmt.where(Application.status == status)
    if region is not None:
        stmt = stmt.where(Application.region == region)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def get_stats(session: AsyncSession, region: Region | None = None) -> dict[str, int]:
    """Statistika - ixtiyoriy ravishda viloyat bo'yicha filtrlash."""
    stmt = select(Application.status, func.count()).group_by(Application.status)
    if region is not None:
        stmt = stmt.where(Application.region == region)
    result = await session.execute(stmt)
    stats = {status.value: 0 for status in ApplicationStatus}
    for status, count in result.all():
        stats[status.value] = count
    stats["total"] = sum(
        v for k, v in stats.items() if k != "total"
    )
    return stats


# ============================================================================
# Admin CRUD
# ============================================================================

async def get_admin_by_region(session: AsyncSession, region: Region) -> Admin | None:
    """Viloyat bo'yicha faol adminni topadi."""
    result = await session.execute(
        select(Admin)
        .where(Admin.region == region, Admin.is_active == True)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_admin_by_telegram_id(session: AsyncSession, telegram_id: int) -> Admin | None:
    """Telegram ID bo'yicha adminni topadi."""
    result = await session.execute(
        select(Admin).where(Admin.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def create_admin(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    region: Region,
) -> Admin:
    """Yangi admin yaratadi."""
    admin = Admin(
        telegram_id=telegram_id,
        full_name=full_name,
        region=region,
    )
    session.add(admin)
    await session.flush()
    return admin


async def update_admin(
    session: AsyncSession,
    admin_id: int,
    full_name: str | None = None,
    region: Region | None = None,
    is_active: bool | None = None,
) -> Admin | None:
    """Adminni yangilaydi."""
    result = await session.execute(
        select(Admin).where(Admin.id == admin_id)
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        return None
    if full_name is not None:
        admin.full_name = full_name
    if region is not None:
        admin.region = region
    if is_active is not None:
        admin.is_active = is_active
    return admin


async def list_admins(session: AsyncSession, active_only: bool = True) -> list[Admin]:
    """Barcha adminlar ro'yxati."""
    stmt = select(Admin).order_by(Admin.region)
    if active_only:
        stmt = stmt.where(Admin.is_active == True)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_applications_by_admin(
    session: AsyncSession,
    admin_telegram_id: int,
    status: ApplicationStatus | None = None,
    limit: int = 10,
) -> list[Application]:
    """Admin uchun tayinlangan murojaatlar."""
    admin = await get_admin_by_telegram_id(session, admin_telegram_id)
    if admin is None:
        return []
    
    stmt = select(Application).options(
        selectinload(Application.user)
    ).where(Application.assigned_admin_id == admin.id)
    
    if status is not None:
        stmt = stmt.where(Application.status == status)
    
    stmt = stmt.order_by(Application.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
