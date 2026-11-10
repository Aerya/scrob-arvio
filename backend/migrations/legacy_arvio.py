"""Repair the one upstream migration skipped by the original ARVIO fork.

Run before Alembic, without stamping or replaying any applied migration.
"""
import asyncio
from sqlalchemy import text
from db import engine

async def repair():
    async with engine.begin() as conn:
        exists = await conn.scalar(text("SELECT to_regclass('public.alembic_version')"))
        if not exists:
            return
        revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        if revision in ("f9a2b3c4d5e6", "a1b2c3d4e5f7"):
            await conn.execute(text("ALTER TABLE media_server_connections ADD COLUMN IF NOT EXISTS plex_watchlist_synced_keys JSONB"))
        # These extra nullable columns are used by the fork scheduler. Old
        # settings are preserved; upstream instances start with auto-push off.
        if await conn.scalar(text("SELECT to_regclass('public.user_settings')")):
            for column in ("bingebase_auto_push_interval", "bingebase_auto_sync_interval"):
                await conn.execute(text(f"ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS {column} FLOAT"))
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(repair())
