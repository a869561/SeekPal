from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse


def ok(data: Any = None, message: str = "OK") -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"success": True, "message": message, "data": data},
    )


def created(data: Any = None, message: str = "Creado") -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"success": True, "message": message, "data": data},
    )


class APIError(HTTPException):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail=message)
