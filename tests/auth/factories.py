from app.auth.models import User


def make_user(**kwargs) -> User:
    """Return an unsaved User instance with sensible defaults.

    Usage:
        user = make_user(email="alice@example.com")
        db_session.add(user)
        await db_session.flush()

    Note: hashed_password defaults to a bcrypt hash of "password123".
    Import lazily to avoid circular import issues before security module exists.
    """
    from app.auth.security import hash_password  # lazy import
    defaults = {
        "email": "test@example.com",
        "full_name": "Test User",
        "hashed_password": hash_password("password123"),
        "is_active": True,
        "is_superadmin": False,
        "preferred_language": "es",
    }
    defaults.update(kwargs)
    return User(**defaults)
