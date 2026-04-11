import hashlib
import hmac
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ProviderCredential


def _derive_key_material(secret: str, salt: bytes, length: int) -> bytes:
    material = b""
    counter = 0
    while len(material) < length:
        chunk = hashlib.pbkdf2_hmac(
            "sha256",
            secret.encode("utf-8"),
            salt + counter.to_bytes(4, "big"),
            120_000,
            dklen=32,
        )
        material += chunk
        counter += 1
    return material[:length]


def _b64_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("utf-8")


def _b64_decode(value: str) -> bytes:
    return urlsafe_b64decode(value.encode("utf-8"))


def encrypt_secret(plain_text: str) -> str:
    settings = get_settings()
    if (
        settings.secret_encryption_key == "dev-only-change-me"
        and not settings.allow_insecure_secret_key
    ):
        raise RuntimeError("SECRET_ENCRYPTION_KEY must be set to a non-default value.")

    nonce = secrets.token_bytes(16)
    plain_bytes = plain_text.encode("utf-8")
    key_material = _derive_key_material(settings.secret_encryption_key, nonce, len(plain_bytes) + 32)
    key_stream = key_material[:len(plain_bytes)]
    mac_key = key_material[len(plain_bytes):]
    encrypted = bytes([left ^ right for left, right in zip(plain_bytes, key_stream)])
    auth_tag = hmac.new(mac_key, nonce + encrypted, hashlib.sha256).digest()
    return ".".join(["v2", _b64_encode(nonce), _b64_encode(encrypted), _b64_encode(auth_tag)])


def decrypt_secret(cipher_text: str) -> str:
    settings = get_settings()
    parts = cipher_text.split(".")
    if len(parts) != 4 or parts[0] != "v2":
        raise ValueError("Unsupported credential format.")
    nonce = _b64_decode(parts[1])
    encrypted = _b64_decode(parts[2])
    provided_tag = _b64_decode(parts[3])
    key_material = _derive_key_material(settings.secret_encryption_key, nonce, len(encrypted) + 32)
    key_stream = key_material[:len(encrypted)]
    mac_key = key_material[len(encrypted):]
    expected_tag = hmac.new(mac_key, nonce + encrypted, hashlib.sha256).digest()
    if not hmac.compare_digest(provided_tag, expected_tag):
        raise ValueError("Credential integrity check failed.")
    plain_bytes = bytes([left ^ right for left, right in zip(encrypted, key_stream)])
    return plain_bytes.decode("utf-8")


async def upsert_provider_key(
    db: AsyncSession,
    *,
    owner_id: str,
    provider: str,
    api_key: str,
) -> ProviderCredential:
    existing = await db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.owner_id == owner_id,
            ProviderCredential.provider == provider,
        )
    )
    encrypted_value = encrypt_secret(api_key)
    masked_last4 = api_key[-4:] if len(api_key) >= 4 else api_key
    if existing is None:
        existing = ProviderCredential(
            owner_id=owner_id,
            provider=provider,
            encrypted_value=encrypted_value,
            key_version="v1",
            last4=masked_last4,
            is_active=True,
        )
        db.add(existing)
    else:
        existing.encrypted_value = encrypted_value
        existing.last4 = masked_last4
        existing.is_active = True
    await db.commit()
    await db.refresh(existing)
    return existing


async def get_provider_credential(
    db: AsyncSession,
    *,
    owner_id: str,
    provider: str,
) -> Optional[ProviderCredential]:
    return await db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.owner_id == owner_id,
            ProviderCredential.provider == provider,
            ProviderCredential.is_active.is_(True),
        )
    )
