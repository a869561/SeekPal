"""Extractor para presentaciones PowerPoint 97-2007 (.ppt).

El formato binario PPT (OLE2) almacena el texto en "átomos" con un tipo
de registro fijo. No se necesita LibreOffice ni herramientas externas.

Tipos de átomo que contienen texto:
  0x0FA0  TextCharsAtom  → UTF-16LE
  0x0FA8  TextBytesAtom  → Latin-1 (Windows-1252)

El flujo "PowerPoint Document" dentro del contenedor OLE2 es una
secuencia plana de registros, cada uno con cabecera de 8 bytes:
  [verInst: 2B][recType: 2B][recLen: 4B][data: recLen B]
"""
from __future__ import annotations

import struct
from pathlib import Path

import olefile

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc

_TEXT_CHARS = 0x0FA0   # UTF-16LE
_TEXT_BYTES = 0x0FA8   # Latin-1

_PPT_STREAM = "PowerPoint Document"


def _parse_atoms(data: bytes) -> list[str]:
    """Extrae todos los átomos de texto de un flujo PPT binario."""
    texts: list[str] = []
    i = 0
    n = len(data)

    while i + 8 <= n:
        _ver_inst, rec_type, rec_len = struct.unpack_from("<HHI", data, i)
        i += 8
        end = i + rec_len
        if end > n:
            break
        payload = data[i:end]

        if rec_type == _TEXT_CHARS:
            try:
                texts.append(payload.decode("utf-16-le"))
            except Exception:
                pass
        elif rec_type == _TEXT_BYTES:
            try:
                texts.append(payload.decode("latin-1"))
            except Exception:
                pass

        i = end

    return [t for t in texts if t.strip()]


class PptExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        with olefile.OleFileIO(str(path)) as ole:
            if not ole.exists(_PPT_STREAM):
                raise ValueError(f"Flujo '{_PPT_STREAM}' no encontrado en {path.name}")
            data = ole.openstream(_PPT_STREAM).read()

        texts = _parse_atoms(data)
        text = "\n".join(texts)
        return ExtractedDoc(text=text, page_map=[], extractor="ppt")

    def supported_extensions(self) -> list[str]:
        return [".ppt"]
