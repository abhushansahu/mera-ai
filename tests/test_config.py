from app.config import get_settings


def test_load_settings_has_defaults() -> None:
    settings = get_settings()

    assert settings.database_url.startswith("postgresql")
    assert settings.default_model != ""


