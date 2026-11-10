import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db import get_db
from models import CollectionSource, Media, Show, SyncJob, SyncStatus, User, UserSettings, WatchEvent
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


async def run_bingebase_push(user_id: int, job_id: int) -> None:
    """Push all historical watched events from Scrob DB to Bingebase Webhook URL."""
    from routers.sync import SyncCancelled, _raise_if_cancelled, _short_error
    from routers.webhooks import _maybe_bingebase_scrobble

    from db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        processed_so_far = 0
        try:
            await _raise_if_cancelled(db, job_id)
            await db.execute(
                update(SyncJob).where(SyncJob.id == job_id).values(status=SyncStatus.running)
            )
            await db.commit()

            result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
            settings = result.scalar_one_or_none()
            if not settings or not settings.bingebase_webhook_url:
                raise ValueError("Configure a valid Bingebase Webhook URL in Settings first")

            events_result = await db.execute(
                select(WatchEvent)
                .options(selectinload(WatchEvent.media))
                .where(WatchEvent.user_id == user_id)
                .order_by(WatchEvent.watched_at.asc())
            )
            events = events_result.scalars().all()
            total_items = len(events)

            await db.execute(
                update(SyncJob).where(SyncJob.id == job_id).values(total_items=total_items)
            )
            await db.commit()

            logger.info("Bingebase push job %s: queued %s watched items.", job_id, total_items)

            succeeded_count = 0
            failed_count = 0

            import httpx
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                for i, event in enumerate(events, 1):
                    if event.media:
                        success = await _maybe_bingebase_scrobble(
                            settings, event.media, "stop", 1.0, db=db, client=http_client, is_push=True
                        )
                        if success:
                            succeeded_count += 1
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1

                    processed_so_far = i
                    if i % 10 == 0 or i == total_items:
                        await db.execute(
                            update(SyncJob).where(SyncJob.id == job_id).values(processed_items=processed_so_far)
                        )
                        await db.commit()
                        await _raise_if_cancelled(db, job_id)

                    if i % 100 == 0 or i == total_items:
                        logger.info("Bingebase push job %s progress: %s/%s processed (%s succeeded, %s failed)", job_id, i, total_items, succeeded_count, failed_count)

                    await asyncio.sleep(0.01)

            final_stats = {
                "submitted": total_items,
                "succeeded": succeeded_count,
                "failed": failed_count,
            }

            if total_items > 0 and succeeded_count == 0:
                err_msg = f"Failed to push history: all {failed_count} items failed to reach Bingebase webhook."
                logger.error("Bingebase push job %s failed: %s", job_id, err_msg)
                await db.execute(
                    update(SyncJob).where(SyncJob.id == job_id).values(
                        status=SyncStatus.failed,
                        processed_items=processed_so_far,
                        error_message=err_msg,
                        stats=final_stats,
                    )
                )
            elif failed_count > 0:
                logger.warning("Bingebase push job %s completed with warnings: %s succeeded, %s failed.", job_id, succeeded_count, failed_count)
                await db.execute(
                    update(SyncJob).where(SyncJob.id == job_id).values(
                        status=SyncStatus.completed,
                        processed_items=processed_so_far,
                        stats=final_stats,
                    )
                )
            else:
                logger.info("Bingebase push job %s completed: %s items pushed.", job_id, succeeded_count)
                await db.execute(
                    update(SyncJob).where(SyncJob.id == job_id).values(
                        status=SyncStatus.completed,
                        processed_items=processed_so_far,
                        stats=final_stats,
                    )
                )
            await db.commit()
        except SyncCancelled:
            logger.info("Bingebase push job %s cancelled", job_id)
            await db.rollback()
            await db.execute(
                update(SyncJob).where(SyncJob.id == job_id).values(
                    status=SyncStatus.cancelled,
                    processed_items=processed_so_far,
                )
            )
            await db.commit()
        except Exception as exc:
            logger.exception("Bingebase push job %s failed", job_id)
            await db.rollback()
            await db.execute(
                update(SyncJob).where(SyncJob.id == job_id).values(
                    status=SyncStatus.failed,
                    error_message=_short_error(exc),
                )
            )
            await db.commit()


@router.post("/push")
async def push_bingebase(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a full background push of all historical watched items to Bingebase."""
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == current_user.id))
    settings = result.scalar_one_or_none()

    if not settings or not settings.bingebase_webhook_url:
        raise HTTPException(
            status_code=400,
            detail="Configure a valid Bingebase Webhook URL in Settings first",
        )

    job = SyncJob(
        user_id=current_user.id,
        source=CollectionSource.bingebase,
        status=SyncStatus.pending,
        job_type="push",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    background_tasks.add_task(run_bingebase_push, current_user.id, job.id)
    return {"status": "started", "job_id": job.id, "message": "Bingebase push is running in the background"}
