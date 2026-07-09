"""SQLAlchemy modellari."""
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ApplicationStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class ApplicationCategory(StrEnum):
    COMPLAINT = "complaint"   # shikoyat
    SUGGESTION = "suggestion" # taklif
    REQUEST = "request"       # ariza
    QUESTION = "question"     # savol


class Region(StrEnum):
    """O'zbekiston viloyatlari."""
    TOSHKENT_SHAHAR = "toshkent_shahar"
    TOSHKENT_VILOYAT = "toshkent_viloyat"
    ANDIJON = "andijon"
    NAMANGAN = "namangan"
    FARGONA = "fargona"
    SIRDARYO = "sirdaryo"
    JIZZAX = "jizzax"
    SAMARQAND = "samarqand"
    NAVOIY = "navoiy"
    BUXORO = "buxoro"
    QASHQADARYO = "qashqadaryo"
    SURXONDARYO = "surxondaryo"
    XORAZM = "xorazm"
    QORAQALPOGISTON = "qoraqalpogiston"


class User(Base):
    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    region: Mapped[Region | None] = mapped_column(
        Enum(Region, name="region", create_constraint=True, native_enum=True),
        nullable=True
    )
    language: Mapped[str] = mapped_column(String(8), default="uz")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    applications: Mapped[list["Application"]] = relationship(back_populates="user")


class Admin(Base):
    """Viloyat adminlari - har bir viloyatga bitta admin biriktiriladi."""
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    region: Mapped[Region] = mapped_column(
        Enum(Region, name="region", create_constraint=True, native_enum=True),
        index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    applications: Mapped[list["Application"]] = relationship(back_populates="assigned_admin")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("bot_users.id", ondelete="CASCADE"))
    category: Mapped[ApplicationCategory] = mapped_column(
        Enum(ApplicationCategory, name="application_category")
    )
    region: Mapped[Region] = mapped_column(
        Enum(Region, name="region", create_constraint=True, native_enum=True),
        index=True
    )
    message_text: Mapped[str] = mapped_column(Text)
    attachment_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"),
        default=ApplicationStatus.NEW,
        index=True,
    )
    admin_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Viloyat admini
    assigned_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    
    # Admin chatdagi xabar ID - javob berilganini kuzatish uchun
    admin_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    admin_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    
    # AI javob bergan bo'lsa
    ai_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_ai_handled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="applications")
    assigned_admin: Mapped["Admin | None"] = relationship(back_populates="applications")
