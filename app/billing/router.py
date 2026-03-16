"""Billing router."""

import logging

import stripe
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_auth
from app.auth.models import User
from app.billing.models import Plan
from app.billing.service import (
    create_checkout_session,
    create_portal_session,
    get_active_subscription,
    get_all_plans,
    get_subscription_by_user,
    handle_payment_failed,
    handle_subscription_created,
    handle_subscription_deleted,
    handle_subscription_updated,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Webhook helpers ────────────────────────────────────────────────────────────


async def handle_payment_intent_succeeded(db: AsyncSession, event_data: dict) -> None:
    """Handle payment_intent.succeeded: confirm booking and record payment."""
    from app.bookings.service import get_booking_by_payment_intent

    pi_id: str = event_data.get("id", "")
    if not pi_id:
        return

    booking = await get_booking_by_payment_intent(db, pi_id)
    if booking is None:
        logger.debug("payment_intent.succeeded: no booking found for pi %s", pi_id)
        return

    # latest_charge is the Charge ID (ch_...)
    charge_id: str | None = event_data.get("latest_charge")

    booking.status = "confirmed"
    booking.payment_status = "paid"
    booking.stripe_payment_id = charge_id
    await db.flush()
    logger.info(
        "Booking %s confirmed via payment_intent.succeeded (charge %s)",
        booking.id,
        charge_id,
    )


# ── Webhook ────────────────────────────────────────────────────────────────────


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as e:
        logger.warning("Invalid Stripe webhook signature: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error("Stripe webhook error: %s", e)
        raise HTTPException(status_code=400, detail="Webhook error")

    event_type: str = event.type
    data_object: dict = event.data.object

    logger.info("Stripe webhook received: %s", event_type)

    if event_type == "customer.subscription.created":
        await handle_subscription_created(db, data_object)
    elif event_type == "customer.subscription.updated":
        await handle_subscription_updated(db, data_object)
    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(db, data_object)
    elif event_type == "invoice.payment_failed":
        await handle_payment_failed(db, data_object)
    elif event_type == "payment_intent.succeeded":
        await handle_payment_intent_succeeded(db, data_object)
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"status": "ok"}


# ── Billing dashboard ──────────────────────────────────────────────────────────


@router.get("/dashboard/billing", response_class=HTMLResponse)
async def billing_page(
    request: Request,
    checkout: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    plans = await get_all_plans(db)
    sub = await get_subscription_by_user(db, user.id)

    current_plan = None
    if sub:
        plan_result = await db.execute(select(Plan).where(Plan.id == sub.plan_id))
        current_plan = plan_result.scalar_one_or_none()

    checkout_success = checkout == "success"

    return templates.TemplateResponse(
        request,
        "dashboard/billing.html",
        {
            "user": user,
            "plans": plans,
            "subscription": sub,
            "current_plan": current_plan,
            "checkout_success": checkout_success,
        },
    )


# ── Subscription status (JSON) ─────────────────────────────────────────────────


@router.get("/dashboard/billing/subscription-status")
async def subscription_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    sub = await get_active_subscription(db, user.id)
    if sub:
        return {"status": "active"}
    return {"status": "none"}


# ── Checkout ───────────────────────────────────────────────────────────────────


@router.post("/dashboard/billing/checkout")
async def start_checkout(
    request: Request,
    plan_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    plan_result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = plan_result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    if not plan.stripe_price_id:
        raise HTTPException(
            status_code=422,
            detail="Este plan no está disponible para pago online aún.",
        )

    base_url = settings.base_url
    success_url = f"{base_url}/dashboard/billing?checkout=success"
    cancel_url = f"{base_url}/dashboard/billing"

    checkout_url = await create_checkout_session(
        db=db,
        user=user,
        plan=plan,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    return RedirectResponse(url=checkout_url, status_code=303)


# ── Portal ─────────────────────────────────────────────────────────────────────


@router.post("/dashboard/billing/portal")
async def open_portal(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    sub = await get_subscription_by_user(db, user.id)
    if not sub:
        raise HTTPException(status_code=404, detail="No tienes una suscripción activa")

    base_url = settings.base_url
    return_url = f"{base_url}/dashboard/billing"

    portal_url = await create_portal_session(
        subscription=sub,
        return_url=return_url,
    )

    return RedirectResponse(url=portal_url, status_code=303)
