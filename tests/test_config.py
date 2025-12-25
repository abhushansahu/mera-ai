from app.config import load_settings


def test_load_settings_has_defaults() -> None:
    settings = load_settings()

    assert settings.openrouter_api_key != ""
    assert settings.database_url.startswith("postgresql")


