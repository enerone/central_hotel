"""Celery tasks for bookings module."""
import logging
from datetime import datetime, timedelta, timezone

import anyio
import stripe
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import Booking
from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)

ORPHAN_TIMEOUT_MINUTES = 30


async def cancel_orphaned_bookings(db: AsyncSession) -> None:
    """Cancel PENDING bookings with a PaymentIntent that are older than ORPHAN_TIMEOUT_MINUTES.

    Called directly in tests (not via Celery worker).
    For each orphaned booking:
    - Set status = 'canceled'
    - Cancel the Stripe PaymentIntent via Stripe API
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ORPHAN_TIMEOUT_MINUTES)

    result = await db.execute(
        select(Booking).where(
            and_(
                Booking.status == "pending",
                Booking.stripe_payment_intent_id.isnot(None),
                Booking.created_at < cutoff,
            )
        )
    )
    orphaned = list(result.scalars().all())

    stripe.api_key = settings.stripe_secret_key

    for booking in orphaned:
        pi_id = booking.stripe_payment_intent_id
        try:
            def _cancel(pi_id=pi_id):
                return stripe.PaymentIntent.cancel(pi_id)

            await anyio.to_thread.run_sync(_cancel)
        except Exception as e:
            logger.warning("Failed to cancel PaymentIntent %s: %s", pi_id, e)

        booking.status = "canceled"
        logger.info("Canceled orphaned booking %s (PaymentIntent %s)", booking.id, pi_id)

    await db.flush()


@celery_app.task(name="bookings.cancel_orphaned_bookings")
def cancel_orphaned_bookings_task() -> None:
    """Celery entry point — creates its own DB session and calls the async function."""
    import asyncio
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await cancel_orphaned_bookings(session)

    asyncio.run(_run())
