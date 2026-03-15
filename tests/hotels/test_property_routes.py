import pytest
from tests.auth.factories import make_user
from tests.hotels.factories import make_property


async def test_properties_list_unauthenticated(async_client):
    response = await async_client.get("/dashboard/properties", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_properties_list_authenticated(async_client, db_session):
    user = make_user(email="proplist@example.com")
    db_session.add(user)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "proplist@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard/properties")
    assert response.status_code == 200
    assert "Propiedades" in response.text or "Properties" in response.text


async def test_create_property_page(async_client, db_session):
    user = make_user(email="newprop@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "newprop@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get("/dashboard/properties/new")
    assert response.status_code == 200
    assert "slug" in response.text.lower() or "nombre" in response.text.lower()


async def test_create_property_success(async_client, db_session):
    user = make_user(email="createprop@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "createprop@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.post(
        "/dashboard/properties/new",
        data={
            "name": "Hotel Test",
            "slug": "hotel-test-create",
            "currency": "ARS",
            "locale": "es",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/dashboard/properties" in response.headers["location"]


async def test_create_property_invalid_slug(async_client, db_session):
    user = make_user(email="badsluq@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "badsluq@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.post(
        "/dashboard/properties/new",
        data={"name": "Hotel", "slug": "AB", "currency": "USD"},
    )
    assert response.status_code == 422


async def test_edit_property_page(async_client, db_session):
    user = make_user(email="editprop@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "editprop@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="edit-me")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.get(f"/dashboard/properties/{prop.id}/edit")
    assert response.status_code == 200


async def test_edit_property_other_user_returns_404(async_client, db_session):
    owner = make_user(email="real_owner@example.com")
    other = make_user(email="other_user@example.com")
    db_session.add_all([owner, other])
    await db_session.flush()

    prop = make_property(user_id=owner.id, slug="not-yours")
    db_session.add(prop)
    await db_session.flush()

    # Log in as other user
    await async_client.post(
        "/login",
        data={"email": "other_user@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.get(f"/dashboard/properties/{prop.id}/edit")
    assert response.status_code == 404


async def test_delete_property(async_client, db_session):
    user = make_user(email="delprop@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "delprop@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="to-delete")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/delete", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard/properties"


async def test_update_property_route(async_client, db_session):
    user = make_user(email="update_route@example.com")
    db_session.add(user)
    await db_session.flush()
    await async_client.post(
        "/login",
        data={"email": "update_route@example.com", "password": "password123"},
        follow_redirects=False,
    )

    prop = make_property(user_id=user.id, slug="update-route-hotel")
    db_session.add(prop)
    await db_session.flush()

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/edit",
        data={"name": "Updated Name", "is_published": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert f"/dashboard/properties/{prop.id}/edit" in response.headers["location"]


async def test_update_property_route_other_user_returns_404(async_client, db_session):
    owner = make_user(email="real_owner2@example.com")
    other = make_user(email="other_user2@example.com")
    db_session.add_all([owner, other])
    await db_session.flush()

    prop = make_property(user_id=owner.id, slug="not-yours-post")
    db_session.add(prop)
    await db_session.flush()

    await async_client.post(
        "/login",
        data={"email": "other_user2@example.com", "password": "password123"},
        follow_redirects=False,
    )

    response = await async_client.post(
        f"/dashboard/properties/{prop.id}/edit",
        data={"name": "Hacked"},
    )
    assert response.status_code == 404
