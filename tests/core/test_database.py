import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

@pytest.mark.asyncio
async def test_get_db_yields_async_session(db_session):
    # db_session fixture is defined in conftest.py (Task 6)
    assert isinstance(db_session, AsyncSession)
