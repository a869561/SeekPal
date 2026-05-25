"""Extractor para documentos Word 97-2007 (.doc).

Parsea el formato binario Word (MS-DOC) sin herramientas externas.

Estrategia:
1. Abre el contenedor OLE2 con olefile.
2. Lee el FIB (File Information Block) del flujo "WordDocument" para
   localizar el CLX (piece table) en el flujo de tabla (0Table/1Table).
3. Itera las piezas del piece table: cada pieza referencia un rango
   de bytes del flujo WordDocument que contiene texto en UTF-16LE o
   en Windows-1252 comprimido.
4. Si el parseo del FIB falla (doc corrupto o variante no estándar),
   cae a un escaneo heurístico de cadenas Unicode en el flujo completo.

Referencias: [MS-DOC] §2.4.1, §2.9.38 (CLX), §2.9.190 (PieceDescriptor).
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

import olefile

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc

_WORD_STREAM  = "WordDocument"
_WIDENT       = 0xA5EC          # magic value in FIBBase.wIdent
_CLX_GRPPRL   = 0x01            # clxt identifier for PrcData (skip)
_CLX_PLCFPCD  = 0x02            # clxt identifier for PlcPcd (piece table)


# ---------------------------------------------------------------------------
# Piece table parsing (MS-DOC §2.9.38 CLX, §2.9.190 PieceDescriptor)
# ---------------------------------------------------------------------------

def _which_table(fib: bytes) -> str:
    """Returns '0Table' or '1Table' based on FIBBase.flags bit 9."""
    flags = struct.unpack_from("<H", fib, 10)[0]
    return "1Table" if (flags & 0x0200) else "0Table"


def _read_u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def _find_clx(fib: bytes) -> tuple[int, int]:
    """
    Returns (fcClx, lcbClx) from FibRgFcLcb97.

    Layout (all sizes in bytes):
      FIBBase    =  32  (offset 0)
      FibRgW97   =  34  (offset 32)
      FibRgLw97  =  88  (offset 66)
      FibRgFcLcb starts at offset 154

    Within FibRgFcLcb97, each entry is [fc:4][lcb:4] = 8 bytes.
    fcClx / lcbClx is at FibRgFcLcb97 entry index 30  →  offset 154 + 30*8 = 394
    """
    BASE = 154 + 30 * 8   # 394
    if len(fib) < BASE + 8:
        raise ValueError("FIB too short to contain fcClx")
    fc  = _read_u32(fib, BASE)
    lcb = _read_u32(fib, BASE + 4)
    return fc, lcb


def _extract_via_piece_table(word_stream: bytes, table_stream: bytes) -> str:
    """
    Parse CLX from the table stream and extract text piece by piece.
    """
    fib = word_stream

    fc_clx, lcb_clx = _find_clx(fib)
    if lcb_clx == 0 or fc_clx + lcb_clx > len(table_stream):
        raise ValueError("CLX out of bounds")

    clx = table_stream[fc_clx: fc_clx + lcb_clx]
    i = 0
    n = len(clx)

    # Skip PrcData entries (clxt == 0x01)
    while i < n and clx[i] == _CLX_GRPPRL:
        i += 1
        if i + 2 > n:
            raise ValueError("Truncated PrcData")
        cb = struct.unpack_from("<H", clx, i)[0]
        i += 2 + cb

    # Expect PlcPcd (clxt == 0x02)
    if i >= n or clx[i] != _CLX_PLCFPCD:
        raise ValueError("PlcPcd not found")
    i += 1
    if i + 4 > n:
        raise ValueError("Truncated PlcPcd length")
    lcb_plc = _read_u32(clx, i)
    i += 4

    plc = clx[i: i + lcb_plc]

    # PlcPcd layout: (n+1) CPs (4 bytes each) followed by n PieceDescriptors (8 bytes each)
    # n = (lcb_plc - 4) // 12   →  (4*(n+1) + 8*n = lcb_plc)
    n_pieces = (len(plc) - 4) // 12
    cp_array = [_read_u32(plc, k * 4) for k in range(n_pieces + 1)]

    parts: list[str] = []
    for k in range(n_pieces):
        pd_off = (n_pieces + 1) * 4 + k * 8      # PieceDescriptor offset in plc
        if pd_off + 8 > len(plc):
            break
        fc_value = _read_u32(plc, pd_off + 2)     # bytes 2-5 of PieceDescriptor

        # bit 30 of fc_value: fCompressed (0 = UTF-16LE, 1 = ANSI compressed)
        f_compressed = bool(fc_value & 0x40000000)
        fc = (fc_value & 0x3FFFFFFF)
        if f_compressed:
            fc >>= 0                               # already halved by spec

        cp_start = cp_array[k]
        cp_end   = cp_array[k + 1]
        char_count = cp_end - cp_start

        if f_compressed:
            raw = word_stream[fc: fc + char_count]
            try:
                parts.append(raw.decode("windows-1252", errors="ignore"))
            except Exception:
                pass
        else:
            byte_count = char_count * 2
            raw = word_stream[fc: fc + byte_count]
            try:
                parts.append(raw.decode("utf-16-le", errors="ignore"))
            except Exception:
                pass

    return "".join(parts)


# ---------------------------------------------------------------------------
# Fallback: heuristic UTF-16LE scan
# ---------------------------------------------------------------------------

_PRINTABLE_U16 = re.compile(
    r"(?:[\x20-\x7E\x09\x0A\x0D -퟿-�]){6,}"
)


def _scan_unicode(data: bytes) -> str:
    """
    Last-resort extraction: decode data as UTF-16LE and keep runs of
    printable characters. Skips the first 512 bytes (FIB area).
    """
    try:
        raw = data[512:].decode("utf-16-le", errors="ignore")
    except Exception:
        return ""
    parts = _PRINTABLE_U16.findall(raw)
    return "\n".join(p.strip() for p in parts if p.strip())


# ---------------------------------------------------------------------------
# Extractor class
# ---------------------------------------------------------------------------

class DocExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        with olefile.OleFileIO(str(path)) as ole:
            if not ole.exists(_WORD_STREAM):
                raise ValueError(f"No se encontró el flujo '{_WORD_STREAM}' en {path.name}")

            word_bytes = ole.openstream(_WORD_STREAM).read()

            # Validate magic
            if len(word_bytes) < 32:
                raise ValueError("WordDocument stream too short")
            wident = struct.unpack_from("<H", word_bytes, 0)[0]
            if wident != _WIDENT:
                raise ValueError(f"Número mágico incorrecto: 0x{wident:04X}")

            # Try proper piece-table extraction
            table_name = _which_table(word_bytes)
            try:
                if ole.exists(table_name):
                    table_bytes = ole.openstream(table_name).read()
                    text = _extract_via_piece_table(word_bytes, table_bytes)
                    if text.strip():
                        # Strip paragraph marks and other Word control chars
                        text = text.replace("\x0D", "\n").replace("\x07", "\n")
                        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
                        return ExtractedDoc(text=text.strip(), page_map=[], extractor="doc")
            except Exception:
                pass

            # Fallback: heuristic scan
            text = _scan_unicode(word_bytes)

        return ExtractedDoc(text=text.strip(), page_map=[], extractor="doc")

    def supported_extensions(self) -> list[str]:
        return [".doc"]
