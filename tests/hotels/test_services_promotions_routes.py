import pytest
from tests.auth.factories import make_user
from tests.hotels.factories import make_property


async def test_services_list(async_client, db_session):
    user = make_user(email="svc_route@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "svc_route@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="svc-hotel-route")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.get(f"/dashboard/properties/{prop.id}/services")
    assert response.status_code == 200
    assert "servicio" in response.text.lower() or "service" in response.text.lower()


async def test_create_service(async_client, db_session):
    user = make_user(email="create_svc@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "create_svc@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="svc-create-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/services/new",
        data={"name_es": "Desayuno", "price": "12.00", "is_included": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 303


async def test_promotions_list(async_client, db_session):
    user = make_user(email="promo_route@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "promo_route@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="promo-hotel-route")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.get(f"/dashboard/properties/{prop.id}/promotions")
    assert response.status_code == 200
    assert "promoci" in response.text.lower() or "promo" in response.text.lower()


async def test_create_promotion(async_client, db_session):
    user = make_user(email="create_promo@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "create_promo@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="promo-create-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/promotions/new",
        data={
            "name_es": "Verano",
            "discount_type": "percent",
            "discount_value": "10.00",
            "valid_from": "2026-01-01",
            "valid_until": "2026-12-31",
            "min_nights": "2",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
