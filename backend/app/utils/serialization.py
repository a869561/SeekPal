"""Serializadores para emitir documentos Beanie en el formato que espera el frontend.

El frontend React (heredado de la implementación Node/Mongoose) consume objetos
con la clave `_id` en lugar de `id`. Beanie usa `id` internamente pero acepta
serializarlo como `_id` mediante el alias estándar de Pydantic.
"""

from datetime import datetime
from typing import Any

from beanie import Document
from bson import ObjectId


def _coerce(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _coerce(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce(v) for v in value]
    return value


def serialize(doc: Document | dict | None) -> dict | None:
    if doc is None:
        return None
    if isinstance(doc, Document):
        raw = doc.model_dump(by_alias=True)
    else:
        raw = dict(doc)
    return _coerce(raw)


def serialize_many(docs: list[Document] | list[dict]) -> list[dict]:
    return [serialize(d) for d in docs]
