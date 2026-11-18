from app.core.config import Settings


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com, https://b.example.com")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_production_flag(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "prod-secret-with-at-least-32-chars-long!")
    assert Settings(_env_file=None).is_production is True
