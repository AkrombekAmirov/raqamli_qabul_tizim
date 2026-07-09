"""add regions and admins

Revision ID: 0002_regions
Revises: 0001_initial
Create Date: 2026-07-02

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_regions"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Region enum yaratish
    region_enum = sa.Enum(
        'toshkent_shahar',
        'toshkent_viloyat',
        'andijon',
        'namangan',
        'fargona',
        'sirdaryo',
        'jizzax',
        'samarqand',
        'navoiy',
        'buxoro',
        'qashqadaryo',
        'surxondaryo',
        'xorazm',
        'qoraqalpogiston',
        name='region',
    )
    region_enum.create(op.get_bind(), checkfirst=True)
    
    # Admins jadvali
    op.create_table(
        'admins',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('region', region_enum, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_admins_telegram_id'),
        'admins',
        ['telegram_id'],
        unique=True,
    )
    op.create_index(
        op.f('ix_admins_region'),
        'admins',
        ['region'],
        unique=False,
    )
    
    # bot_users jadvaliga region qo'shish
    op.add_column(
        'bot_users',
        sa.Column('region', region_enum, nullable=True),
    )
    
    # applications jadvaliga yangi ustunlar qo'shish
    op.add_column(
        'applications',
        sa.Column('region', region_enum, nullable=True),
    )
    op.add_column(
        'applications',
        sa.Column(
            'assigned_admin_id',
            sa.Integer(),
            sa.ForeignKey('admins.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.add_column(
        'applications',
        sa.Column('admin_message_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'applications',
        sa.Column('admin_chat_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'applications',
        sa.Column('ai_response', sa.Text(), nullable=True),
    )
    op.add_column(
        'applications',
        sa.Column('is_ai_handled', sa.Boolean(), nullable=False, server_default='false'),
    )
    
    # Region indeksi
    op.create_index(
        op.f('ix_applications_region'),
        'applications',
        ['region'],
        unique=False,
    )


def downgrade() -> None:
    # Indekslarni o'chirish
    op.drop_index(op.f('ix_applications_region'), table_name='applications')
    
    # applications ustunlarini o'chirish
    op.drop_column('applications', 'is_ai_handled')
    op.drop_column('applications', 'ai_response')
    op.drop_column('applications', 'admin_chat_id')
    op.drop_column('applications', 'admin_message_id')
    op.drop_column('applications', 'assigned_admin_id')
    op.drop_column('applications', 'region')
    
    # bot_users ustunini o'chirish
    op.drop_column('bot_users', 'region')
    
    # admins jadvalini o'chirish
    op.drop_index(op.f('ix_admins_region'), table_name='admins')
    op.drop_index(op.f('ix_admins_telegram_id'), table_name='admins')
    op.drop_table('admins')
    
    # Region enum o'chirish
    sa.Enum(name='region').drop(op.get_bind(), checkfirst=True)
