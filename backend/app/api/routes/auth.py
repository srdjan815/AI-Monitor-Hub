from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.core.security import authenticate_token, current_principal

router = APIRouter(prefix="/auth", tags=["authentication"])
session_router = APIRouter(prefix="/auth", tags=["authentication"])


class SessionLogin(BaseModel):
    token: str = Field(min_length=1, max_length=16_384)


@session_router.post("/session", status_code=204, summary="Otvori bezbednu sesiju")
async def create_session(payload: SessionLogin, response: Response) -> None:
    authenticate_token(payload.token.strip().removeprefix("Bearer ").strip())
    response.set_cookie(
        settings.auth_session_cookie_name,
        payload.token.strip().removeprefix("Bearer ").strip(),
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
        path=settings.api_prefix,
        max_age=settings.auth_token_ttl_seconds,
    )


@session_router.delete("/session", status_code=204, summary="Zatvori sesiju")
async def delete_session(response: Response) -> None:
    response.delete_cookie(
        settings.auth_session_cookie_name,
        path=settings.api_prefix,
        secure=settings.app_env == "production",
        httponly=True,
        samesite="strict",
    )


class CurrentPrincipalRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject: str
    roles: list[str]
    permissions: list[str]
    actor_type: str


@router.get(
    "/me",
    response_model=CurrentPrincipalRead,
    summary="Prikaži trenutni autentifikovani identitet",
    description=(
        "Vraća identitet, uloge i efektivne dozvole koje je backend utvrdio "
        "iz Bearer tokena. Token i tajni podaci se nikada ne vraćaju."
    ),
)
async def current_identity() -> CurrentPrincipalRead:
    principal = current_principal()
    if principal is None:  # Zaštitna grana; authorize_request garantuje principal.
        raise RuntimeError("Authenticated principal is unavailable")
    return CurrentPrincipalRead(
        subject=principal.subject,
        roles=list(principal.roles),
        permissions=sorted(principal.permissions),
        actor_type=principal.actor_type,
    )
