from __future__ import annotations

from typing import Any
import asyncio


async def health_echo(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "echo": payload,
        "handled": True,
    }


async def test(payload: dict[str, Any]) -> dict[str, Any]:
    await asyncio.sleep(1)

    return {
        "success": True,
        "message": payload.get("message"),
        "handled_by": "test_handler",
    }


HANDLERS = {
    "system.health_echo": health_echo,
    "test": test,
}