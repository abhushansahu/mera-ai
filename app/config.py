from app.infrastructure.config.settings import get_settings, Settings

_settings_instance: Settings | None = None


def _get_settings_instance() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = get_settings()
    return _settings_instance


settings = _get_settings_instance()

__all__ = ["settings", "Settings", "get_settings"]
