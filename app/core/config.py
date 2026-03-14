from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = "dev-secret-key-change-in-production"
    base_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://hotel:hotel@localhost:5432/hotel"
    database_url_sync: str = "postgresql://hotel:hotel@localhost:5432/hotel"
    test_database_url: str = "postgresql+asyncpg://hotel:hotel@localhost:5432/hotel_test"

    redis_url: str = "redis://localhost:6379/0"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_publishable_key: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""

    resend_api_key: str = ""
    email_from: str = "noreply@localhost"

    superadmin_email: str = "admin@localhost"
    superadmin_password: str = "change-me"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


settings = Settings()
