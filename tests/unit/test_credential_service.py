from app.config import get_settings
from app.services.credential_service import decrypt_secret, encrypt_secret


def test_encrypt_and_decrypt_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost:5432/db")
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "unit-test-secret-key")
    monkeypatch.setenv("ALLOW_INSECURE_SECRET_KEY", "false")
    get_settings.cache_clear()

    secret = "sk-test-123456"
    encrypted = encrypt_secret(secret)
    decrypted = decrypt_secret(encrypted)

    assert encrypted != secret
    assert decrypted == secret


def test_default_secret_rejected_when_hardening_enabled(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost:5432/db")
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "dev-only-change-me")
    monkeypatch.setenv("ALLOW_INSECURE_SECRET_KEY", "false")
    get_settings.cache_clear()

    try:
        encrypt_secret("abc")
    except RuntimeError as exc:
        assert "SECRET_ENCRYPTION_KEY" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError when using default secret key.")
