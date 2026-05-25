"""Servicio de chunking recursivo por separadores.

Estrategia inspirada en RecursiveCharacterTextSplitter (benchmark Vecta Team,
69% accuracy con chunk 512/overlap 64).

`chunk_size` y `overlap` se expresan en tokens aproximados; internamente se
convierten a caracteres con 1 token ≈ 4 chars (válido para es/en en BPE).
"""

from __future__ import annotations

from app.services.rag.types import Chunk, ExtractedDoc

# Probados en orden: si ninguno funciona se corta por max_chars (path sin
# separador). NO incluir "" aqui: str.split("") lanza ValueError y rompe la
# indexacion en textos sin espacios > max_chars (base64, JSON minificado, etc.).
SEPARATORS = ["\n\n", "\n", ". ", " "]
CHARS_PER_TOKEN = 4


def _find_page_for_offset(offset: int, page_map: list[tuple[int, int]]) -> int | None:
    if not page_map:
        return None
    page = page_map[0][0]
    for p, start in page_map:
        if offset >= start:
            page = p
        else:
            break
    return page


def _split_recursive(text: str, max_chars: int, separators: list[str]) -> list[tuple[str, int]]:
    """Devuelve [(fragmento, offset_relativo_dentro_de_text), ...]."""
    if len(text) <= max_chars:
        return [(text, 0)]

    if not separators:
        out: list[tuple[str, int]] = []
        for i in range(0, len(text), max_chars):
            out.append((text[i:i + max_chars], i))
        return out

    sep, rest_seps = separators[0], separators[1:]
    parts = text.split(sep)
    offsets: list[int] = []
    cursor = 0
    for part in parts:
        offsets.append(cursor)
        cursor += len(part) + len(sep)

    out: list[tuple[str, int]] = []
    buf = ""
    buf_offset = 0
    for part, off in zip(parts, offsets):
        candidate = (buf + sep + part) if buf else part
        if len(candidate) <= max_chars:
            if not buf:
                buf_offset = off
            buf = candidate
        else:
            if buf:
                out.append((buf, buf_offset))
            if len(part) > max_chars:
                for piece, piece_off in _split_recursive(part, max_chars, rest_seps):
                    out.append((piece, off + piece_off))
                buf = ""
            else:
                buf = part
                buf_offset = off
    if buf:
        out.append((buf, buf_offset))
    return out


def chunk_text(doc: ExtractedDoc, chunk_size: int, overlap: int) -> list[Chunk]:
    """Trocea `doc.text` en chunks de ~chunk_size tokens con overlap."""
    max_chars = chunk_size * CHARS_PER_TOKEN
    overlap_chars = overlap * CHARS_PER_TOKEN

    if not doc.text.strip():
        return []

    raw_chunks = _split_recursive(doc.text, max_chars, SEPARATORS)

    chunks: list[Chunk] = []
    for idx, (frag, off) in enumerate(raw_chunks):
        if not frag.strip():
            continue
        start = off
        end = off + len(frag)
        if idx > 0 and overlap_chars > 0:
            start = max(0, start - overlap_chars)
            frag = doc.text[start:end]
        chunks.append(
            Chunk(
                text=frag,
                chunk_idx=idx,
                offset_start=start,
                offset_end=end,
                page=_find_page_for_offset(start, doc.page_map),
            )
        )
    return chunks
