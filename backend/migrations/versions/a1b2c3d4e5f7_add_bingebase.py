"""add Bingebase integration

Revision ID: a1b2c3d4e5f7
Revises: f9a2b3c4d5e6
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f7"
down_revision = "f9a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE collectionsource ADD VALUE IF NOT EXISTS 'bingebase'")
    op.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS bingebase_webhook_url VARCHAR(500)")
    op.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS bingebase_api_key VARCHAR(255)")
    op.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS bingebase_sync_watched BOOLEAN DEFAULT TRUE NOT NULL")
    op.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS bingebase_scrobble BOOLEAN DEFAULT TRUE NOT NULL")
    op.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS bingebase_push_watched BOOLEAN DEFAULT FALSE NOT NULL")
    op.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS bingebase_push_ratings BOOLEAN DEFAULT FALSE NOT NULL")
    op.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS bingebase_auto_sync_interval FLOAT")
    op.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS bingebase_auto_push_interval FLOAT")


def downgrade() -> None:
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS bingebase_auto_push_interval")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS bingebase_auto_sync_interval")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS bingebase_push_ratings")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS bingebase_push_watched")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS bingebase_scrobble")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS bingebase_sync_watched")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS bingebase_api_key")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS bingebase_webhook_url")
