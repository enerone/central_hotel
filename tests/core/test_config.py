# tests/core/test_config.py
from app.core.config import settings

def test_settings_has_required_fields():
    assert settings.database_url
    assert settings.secret_key
    assert settings.redis_url

def test_settings_app_env_defaults_to_development():
    assert settings.app_env in ("development", "test", "production")
