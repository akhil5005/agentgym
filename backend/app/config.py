"""Settings, read from the environment with pydantic-settings.

One object, built once at import time, so every module reads the same values and
nothing reaches into `os.environ` directly.
"""

from __future__ import annotations

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Everything the backend needs to know about its environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # "dev" relaxes a couple of rules for local work; "prod" tightens them.
    env: str = "dev"

    # SQLite by default so the project runs with no setup at all.
    database_url: str = "sqlite:///./agentgym.db"

    # Shared secret for the two write endpoints. The runner sends it as
    # X-API-Key when uploading results.
    ingest_api_key: str = "dev-key"

    # The single browser origin allowed to call this API.
    frontend_origin: str = "http://localhost:3000"

    @field_validator("database_url")
    @classmethod
    def normalise_database_url(cls, value: str) -> str:
        """Rewrite the legacy `postgres://` prefix to the driver we install.

        Hosting providers (Render, Neon, Heroku) hand out URLs starting with
        `postgres://` or `postgresql://`. SQLAlchemy would then pick its default
        driver, which we do not install. Pointing it at psycopg 3 explicitly
        turns a confusing import error at startup into something that just works.
        """
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @model_validator(mode="after")
    def refuse_the_default_key_in_production(self) -> "Settings":
        """In prod, refuse to start rather than run with the dev key.

        Failing at startup is loud and obvious. Running with a publicly known
        API key would be silent, and anyone could write to the database.
        """
        if self.env == "prod" and self.ingest_api_key in ("", "dev-key"):
            raise ValueError(
                "INGEST_API_KEY must be set to a real secret when ENV=prod "
                "(it is still the default 'dev-key')"
            )
        return self

    @property
    def is_dev(self) -> bool:
        return self.env != "prod"

    @property
    def allowed_origins(self) -> list[str]:
        """Origins the browser may call us from.

        Localhost is added in dev only, so a deployed backend never trusts a
        page served from someone else's machine.
        """
        origins = [self.frontend_origin]
        if self.is_dev and "http://localhost:3000" not in origins:
            origins.append("http://localhost:3000")
        return origins


settings = Settings()
