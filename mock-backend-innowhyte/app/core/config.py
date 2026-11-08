from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_CSV_FIELDS = ("CORS_ORIGINS", "JWT_ALGORITHMS", "ADMIN_EMAILS")
_OPTIONAL_STR_FIELDS = (
    "DATABASE_URL",
    "MIGRATIONS_DATABASE_URL",
    "WORKOS_CLIENT_ID",
    "WORKOS_API_KEY",
    "WORKOS_ISSUER",
    "WORKOS_ORGANIZATION_ID",
    "JWT_JWKS_URL",
    "JWT_SECRET",
    "JWT_AUDIENCE",
    "JWT_ISSUER",
    "BETTER_AUTH_URL",
)


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    PROJECT_NAME: str = "User API"
    ENVIRONMENT: str = "local"  # local | staging | production
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Database. DATABASE_URL (e.g. Neon) wins; otherwise the URL is built from POSTGRES_*.
    DATABASE_URL: str | None = None
    # Optional direct (non-pooled) URL used only by Alembic.
    # Neon recommends direct connections for migrations (host without "-pooler").
    MIGRATIONS_DATABASE_URL: str | None = None
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "user_api"
    DB_ECHO: bool = False

    # Auth provider. Login happens in the frontend; this API only verifies the provider's access tokens.
    # Must match AUTH_PROVIDER in the Next.js app: the name is stored in users.auth_provider.
    #   workos      -> WorkOS AuthKit (JWKS + issuer derived from WORKOS_CLIENT_ID)
    #   better-auth -> Better Auth's JWT plugin in the Next.js app (all settings derived from BETTER_AUTH_URL)
    #   jwt         -> any other provider that issues JWTs (JWKS or HS256), and the test suite
    AUTH_PROVIDER: Literal["workos", "better-auth", "jwt"] = "workos"

    # Better Auth (AUTH_PROVIDER=better-auth): the Next.js app's public URL, same as its BETTER_AUTH_URL.
    # Keys are read from {BETTER_AUTH_URL}/api/auth/jwks; issuer and audience are this URL.
    BETTER_AUTH_URL: str | None = None

    WORKOS_CLIENT_ID: str | None = None
    WORKOS_API_KEY: SecretStr | None = None
    WORKOS_API_BASE_URL: str = "https://api.workos.com"
    # Only needed with a custom auth domain. Defaults to {WORKOS_API_BASE_URL}/user_management/{client_id}.
    WORKOS_ISSUER: str | None = None
    # The WorkOS organization for this deployment (Admin Portal links, Audit Logs).
    WORKOS_ORGANIZATION_ID: str | None = None
    # Also send audit events to WorkOS Audit Logs (free in staging, billed in production).
    WORKOS_AUDIT_LOGS_ENABLED: bool = False

    # Generic JWT settings (AUTH_PROVIDER=jwt). Use JWKS (RS256, recommended) OR a shared secret (HS256).
    JWT_JWKS_URL: str | None = None
    JWT_SECRET: SecretStr | None = None
    JWT_ALGORITHMS: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["RS256"])
    JWT_AUDIENCE: str | None = None
    JWT_ISSUER: str | None = None

    # Allowed clock skew when checking exp/iat.
    JWT_LEEWAY_SECONDS: int = Field(default=10, ge=0, le=60)

    # Break-glass admins: always admin, cannot be demoted or deactivated from the admin board.
    ADMIN_EMAILS: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalise_raw_values(cls, data: dict) -> dict:
        for key in _CSV_FIELDS:
            value = data.get(key)
            if isinstance(value, str):
                data[key] = [v.strip() for v in value.split(",") if v.strip()]
        for key in _OPTIONAL_STR_FIELDS:
            if isinstance(data.get(key), str) and not data[key].strip():
                data[key] = None
        return data

    @model_validator(mode="after")
    def _check_auth_config(self) -> "Settings":
        if self.AUTH_PROVIDER == "workos":
            if not (self.WORKOS_CLIENT_ID and self.WORKOS_API_KEY):
                raise ValueError("AUTH_PROVIDER=workos requires WORKOS_CLIENT_ID and WORKOS_API_KEY")
        elif self.AUTH_PROVIDER == "better-auth":
            if not self.BETTER_AUTH_URL:
                raise ValueError("AUTH_PROVIDER=better-auth requires BETTER_AUTH_URL (the Next.js app URL)")
            self.BETTER_AUTH_URL = self.BETTER_AUTH_URL.rstrip("/")
        elif not (self.JWT_JWKS_URL or self.JWT_SECRET):
            raise ValueError("AUTH_PROVIDER=jwt requires JWT_JWKS_URL or JWT_SECRET")
        if self.WORKOS_AUDIT_LOGS_ENABLED and not self.WORKOS_ORGANIZATION_ID:
            raise ValueError("WORKOS_AUDIT_LOGS_ENABLED=true requires WORKOS_ORGANIZATION_ID")
        self.ADMIN_EMAILS = [e.lower() for e in self.ADMIN_EMAILS]
        return self

    @property
    def database_url(self) -> str:
        """Runtime database URL (libpq style, e.g. postgresql://...?sslmode=require)."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return str(
            PostgresDsn.build(
                scheme="postgresql",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    @property
    def migrations_database_url(self) -> str:
        return self.MIGRATIONS_DATABASE_URL or self.database_url

    @property
    def workos_issuer(self) -> str:
        return self.WORKOS_ISSUER or f"{self.WORKOS_API_BASE_URL}/user_management/{self.WORKOS_CLIENT_ID}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
