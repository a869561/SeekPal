from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse


class RagErrorCode(str, Enum):
    EMBEDDING_FAILED = "embedding_failed"
    RETRIEVAL_FAILED = "retrieval_failed"
    GENERATION_FAILED = "generation_failed"
    OLLAMA_UNAVAILABLE = "ollama_unavailable"
    INVALID_QUESTION = "invalid_question"
    NO_RESULTS = "no_results"


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
