"""Tests for the dashboard widget config page."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.billing.helpers import make_active_sub_for_user


@pytest.fixture
async def auth_client_with_prop(async_client: AsyncClient, db_session: AsyncSession):
    from app.auth.models import User
    from app.hotels.models import Property
    import bcrypt

    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"wconf-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hashed,
        full_name="Config Owner",
    )
    db_session.add(user)
    await db_session.flush()
    await make_active_sub_for_user(db_session, user.id)

    prop = Property(
        id=uuid.uuid4(),
        user_id=user.id,
        slug=f"wconf-{uuid.uuid4().hex[:8]}",
        name="Config Hotel",
        description={"es": "Hotel", "en": "Hotel"},
        currency="USD",
        locale="es",
        is_published=False,
        widget_config={
            "primary_color": "#3B82F6",
            "sections": {
                "rooms": {"enabled": True, "standalone": False},
                "rentals": {"enabled": False, "standalone": False},
                "amenities": {"enabled": False, "standalone": False},
            },
        },
    )
    db_session.add(prop)
    await db_session.flush()

    resp = await async_client.post(
        "/login", data={"email": user.email, "password": "pw"}, follow_redirects=True
    )
    assert resp.status_code == 200
    return async_client, prop


@pytest.mark.asyncio
async def test_widget_config_page_200(auth_client_with_prop):
    client, prop = auth_client_with_prop
    resp = await client.get(f"/dashboard/properties/{prop.id}/widget")
    assert resp.status_code == 200
    assert prop.slug in resp.text


@pytest.mark.asyncio
async def test_widget_config_page_shows_iframe_snippet(auth_client_with_prop):
    client, prop = auth_client_with_prop
    resp = await client.get(f"/dashboard/properties/{prop.id}/widget")
    assert resp.status_code == 200
    assert "iframe" in resp.text
    assert prop.slug in resp.text


@pytest.mark.asyncio
async def test_widget_config_save_primary_color(auth_client_with_prop, db_session):
    client, prop = auth_client_with_prop
    resp = await client.post(
        f"/dashboard/properties/{prop.id}/widget",
        data={"primary_color": "#FF5733"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    await db_session.refresh(prop)
    assert prop.widget_config.get("primary_color") == "#FF5733"


@pytest.mark.asyncio
async def test_widget_config_404_for_other_owner(auth_client_with_prop, db_session):
    """Cannot access another owner's widget config."""
    client, prop = auth_client_with_prop
    resp = await client.get(f"/dashboard/properties/{uuid.uuid4()}/widget")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_widget_config_save_section_flags(auth_client_with_prop, db_session):
    """Toggling rentals_enabled=on saves sections.rentals.enabled=True."""
    client, prop = auth_client_with_prop
    resp = await client.post(
        f"/dashboard/properties/{prop.id}/widget",
        data={"primary_color": "#3B82F6", "rentals_enabled": "on"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    await db_session.refresh(prop)
    assert prop.widget_config["sections"]["rentals"]["enabled"] is True
    assert prop.widget_config["sections"]["amenities"]["enabled"] is False  # not submitted
