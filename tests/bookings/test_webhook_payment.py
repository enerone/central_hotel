"""Tests for payment_intent.succeeded webhook handler."""
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.bookings.factories import make_booking
from tests.billing.helpers import make_active_sub_for_user


@pytest.fixture
async def property_with_pending_payment_booking(db_session: AsyncSession):
    """Setup: user + sub + property + room + pending booking with PaymentIntent."""
    from app.auth.models import User
    from app.hotels.models import Property, Room
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"owner-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, user.id)

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"hotel-{uuid.uuid4().hex[:8]}",
        name="Hotel",
        description={"es": "H", "en": "H"},
        currency="USD",
        locale="es",
    )
    db_session.add(prop)
    await db_session.flush()

    room = Room(
        id=uuid.uuid4(),
        property_id=prop.id,
        name={"es": "H", "en": "R"},
        description={"es": "D", "en": "D"},
        capacity=2,
        base_price=Decimal("100.00"),
        amenities=[],
        is_active=True,
    )
    db_session.add(room)
    await db_session.flush()

    booking = make_booking(
        property_id=prop.id,
        room_id=room.id,
        check_in=date.today() + timedelta(days=5),
        check_out=date.today() + timedelta(days=7),
        status="pending",
        payment_status="unpaid",
        stripe_payment_intent_id="pi_test_webhook_001",
    )
    db_session.add(booking)
    await db_session.flush()
    return booking


@pytest.mark.asyncio
async def test_payment_intent_succeeded_confirms_booking(
    async_client: AsyncClient,
    db_session: AsyncSession,
    property_with_pending_payment_booking,
):
    """payment_intent.succeeded webhook confirms booking and sets payment_status=paid."""
    booking = property_with_pending_payment_booking

    event_payload = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test_webhook_001",
                "latest_charge": "ch_test_charge_001",
            }
        },
    }

    # Construct a fake Stripe event that bypasses signature verification
    fake_event = MagicMock()
    fake_event.type = "payment_intent.succeeded"
    fake_event.data.object = event_payload["data"]["object"]

    with patch("app.billing.router.stripe.Webhook.construct_event", return_value=fake_event):
        resp = await async_client.post(
            "/webhooks/stripe",
            content=json.dumps(event_payload),
            headers={"stripe-signature": "fake_sig", "content-type": "application/json"},
        )

    assert resp.status_code == 200
    await db_session.refresh(booking)
    assert booking.status == "confirmed"
    assert booking.payment_status == "paid"
    assert booking.stripe_payment_id == "ch_test_charge_001"


@pytest.mark.asyncio
async def test_payment_intent_succeeded_unknown_pi_is_ignored(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """payment_intent.succeeded for unknown PaymentIntent returns 200 (idempotent)."""
    fake_event = MagicMock()
    fake_event.type = "payment_intent.succeeded"
    fake_event.data.object = {
        "id": "pi_unknown_999",
        "latest_charge": "ch_unknown_999",
    }

    with patch("app.billing.router.stripe.Webhook.construct_event", return_value=fake_event):
        resp = await async_client.post(
            "/webhooks/stripe",
            content="{}",
            headers={"stripe-signature": "fake_sig", "content-type": "application/json"},
        )

    assert resp.status_code == 200
