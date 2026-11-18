from app.core.config import Settings


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com, https://b.example.com")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_production_flag(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "prod-secret-with-at-least-32-chars-long!")
    assert Settings(_env_file=None).is_production is True


def test_database_url_normalizes_render_postgres_schemes(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")
    assert Settings(_env_file=None).database_url == "postgresql+psycopg://u:p@host:5432/db"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    assert Settings(_env_file=None).database_url == "postgresql+psycopg://u:p@host:5432/db"
