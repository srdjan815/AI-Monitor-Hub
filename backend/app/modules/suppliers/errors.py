from typing import NoReturn

from fastapi import HTTPException


def supplier_error(status_code: int, code: str, message: str) -> NoReturn:
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


__all__ = ["supplier_error"]
