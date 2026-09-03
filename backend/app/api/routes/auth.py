from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.core.security import current_principal

router = APIRouter(prefix="/auth", tags=["authentication"])


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
