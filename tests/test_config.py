from app.config import get_settings


def test_load_settings_has_defaults() -> None:
    settings = get_settings()

    assert settings.openrouter_api_key != ""
    assert settings.database_url.startswith("postgresql")


