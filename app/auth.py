from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: str
    token_id: str
    is_service: bool = False


@lru_cache()
def _token_map() -> dict[str, str]:
    settings = get_settings()
    parsed: dict[str, str] = {}
    raw = settings.auth_tokens or ""
    for pair in raw.split(","):
        item = pair.strip()
        if not item:
            continue
        if ":" not in item:
            continue
        user_id, token = item.split(":", 1)
        if user_id.strip() and token.strip():
            parsed[token.strip()] = user_id.strip()
    return parsed


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


async def get_optional_principal(
    authorization: str | None = Header(default=None),
    x_internal_service_key: str | None = Header(default=None),
) -> AuthPrincipal:
    settings = get_settings()
    token = _extract_bearer_token(authorization)
    mapped_tokens = _token_map()

    if token and token in mapped_tokens:
        return AuthPrincipal(user_id=mapped_tokens[token], token_id="bearer")

    if settings.internal_service_key and x_internal_service_key == settings.internal_service_key:
        return AuthPrincipal(user_id="internal-service", token_id="internal", is_service=True)

    if settings.auth_required:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid bearer token required.",
        )

    # Development fallback for local workflows.
    return AuthPrincipal(user_id="default-user", token_id="anonymous")


async def get_required_principal(principal: AuthPrincipal = Depends(get_optional_principal)) -> AuthPrincipal:
    return principal

