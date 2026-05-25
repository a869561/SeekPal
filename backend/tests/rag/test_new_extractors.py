"""Tests de los extractores nuevos: RTF, EPUB, PPT, DOC."""
from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import olefile
import openpyxl
import pytest

from app.services.rag.extractors.epub import EpubExtractor
from app.services.rag.extractors.ppt import PptExtractor
from app.services.rag.extractors.rtf import RtfExtractor


# ---------------------------------------------------------------------------
# RTF
# ---------------------------------------------------------------------------

@pytest.fixture
def rtf_file(tmp_path: Path) -> Path:
    p = tmp_path / "doc.rtf"
    # RTF mínimo con texto en español
    p.write_text(
        r"{\rtf1\ansi\deff0"
        r"{\fonttbl{\f0 Arial;}}"
        r"\f0\fs24 Hola mundo desde RTF. El universo es vasto.}"
        , encoding="latin-1"
    )
    return p


def test_rtf_extracts_text(rtf_file):
    doc = RtfExtractor().extract(rtf_file)
    assert "Hola" in doc.text
    assert "universo" in doc.text
    assert doc.extractor == "rtf"


def test_rtf_supported_extensions():
    assert ".rtf" in RtfExtractor().supported_extensions()


# ---------------------------------------------------------------------------
# EPUB
# ---------------------------------------------------------------------------

def _build_epub(tmp_path: Path, content: str) -> Path:
    """Construye un EPUB mínimo válido sin ebooklib (zip manual)."""
    p = tmp_path / "book.epub"
    chapter_html = (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<!DOCTYPE html><html xmlns='http://www.w3.org/1999/xhtml'>"
        f"<body><p>{content}</p></body></html>"
    )
    opf = """<?xml version='1.0' encoding='utf-8'?>
<package xmlns='http://www.idpf.org/2007/opf' version='2.0' unique-identifier='uid'>
  <metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>
    <dc:title>Test Book</dc:title>
    <dc:identifier id='uid'>test-id</dc:identifier>
    <dc:language>es</dc:language>
  </metadata>
  <manifest>
    <item id='ch1' href='ch1.xhtml' media-type='application/xhtml+xml'/>
    <item id='ncx' href='toc.ncx' media-type='application/x-dtbncx+xml'/>
  </manifest>
  <spine toc='ncx'><itemref idref='ch1'/></spine>
</package>"""
    ncx = """<?xml version='1.0' encoding='utf-8'?>
<ncx xmlns='http://www.daisy.org/z3986/2005/ncx/' version='2005-1'>
  <head><meta name='dtb:uid' content='test-id'/></head>
  <docTitle><text>Test Book</text></docTitle>
  <navMap><navPoint id='np1' playOrder='1'>
    <navLabel><text>Cap 1</text></navLabel>
    <content src='ch1.xhtml'/>
  </navPoint></navMap>
</ncx>"""
    with zipfile.ZipFile(str(p), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   "<?xml version='1.0'?>"
                   "<container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>"
                   "<rootfiles><rootfile full-path='OEBPS/content.opf'"
                   " media-type='application/oebps-package+xml'/></rootfiles></container>")
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/toc.ncx", ncx)
        z.writestr("OEBPS/ch1.xhtml", chapter_html)
    return p


def test_epub_extracts_text(tmp_path):
    p = _build_epub(tmp_path, "El universo y la inteligencia artificial")
    doc = EpubExtractor().extract(p)
    assert "universo" in doc.text
    assert "inteligencia" in doc.text
    assert doc.extractor == "epub"


def test_epub_strips_html_tags(tmp_path):
    p = _build_epub(tmp_path, "<strong>Texto</strong> sin etiquetas <em>HTML</em>")
    doc = EpubExtractor().extract(p)
    assert "<strong>" not in doc.text
    assert "Texto" in doc.text


def test_epub_supported_extensions():
    assert ".epub" in EpubExtractor().supported_extensions()


# ---------------------------------------------------------------------------
# PPT (binario)
# ---------------------------------------------------------------------------

def _make_ppt_atom(rec_type: int, payload: bytes) -> bytes:
    """Crea un átomo PPT con cabecera de 8 bytes."""
    ver_inst = 0x0000            # recVersion=0, recInstance=0
    return struct.pack("<HHI", ver_inst, rec_type, len(payload)) + payload


def _build_ppt(tmp_path: Path, texts: list[str]) -> Path:
    """Construye un OLE2 mínimo con un flujo 'PowerPoint Document' con átomos de texto."""
    import io
    import olefile

    TEXT_CHARS = 0x0FA0
    TEXT_BYTES = 0x0FA8

    # Construir el flujo: un átomo TextCharsAtom (UTF-16LE) por texto
    stream_data = b""
    for i, t in enumerate(texts):
        if i % 2 == 0:
            stream_data += _make_ppt_atom(TEXT_CHARS, t.encode("utf-16-le"))
        else:
            stream_data += _make_ppt_atom(TEXT_BYTES, t.encode("latin-1"))

    # OLE2 mini_stream_cutoff = 0x1000 (4096 bytes): streams más pequeños van al
    # mini-stream, que nuestro OLE2 mínimo no implementa. Forzamos tamaño > 4096
    # añadiendo un átomo relleno de tipo desconocido (0x0FFF) que _parse_atoms ignora.
    MIN_SIZE = 0x1001  # justo por encima del cutoff
    if len(stream_data) < MIN_SIZE:
        pad_payload = MIN_SIZE - len(stream_data) - 8  # 8 bytes de cabecera de átomo
        stream_data += struct.pack("<HHI", 0, 0x0FFF, pad_payload) + b"\x00" * pad_payload

    p = tmp_path / "pres.ppt"
    _write_minimal_ole2(p, "PowerPoint Document", stream_data)
    return p


def _write_minimal_ole2(path: Path, stream_name: str, data: bytes) -> None:
    """
    Escribe un archivo OLE2 mínimo con un único flujo usando el módulo
    'compoundfiles' incluido en olefile ≥0.47 para escritura.
    Si no está disponible, usa una aproximación directa.
    """
    # olefile es solo lectura; usamos cfb manual mínimo
    # Alternativa: python-pptx crea .pptx pero no .ppt.
    # Para el test, creamos el .ppt real vía struct (formato minimal).
    # OLE2 CFBF sector size=512, 1 FAT sector + 1 directory sector + 1 data sector
    import io

    SECT_SIZE = 512
    ENDOFCHAIN = 0xFFFFFFFE
    FREESECT   = 0xFFFFFFFF
    DIFSECT    = 0xFFFFFFFC
    FATSECT    = 0xFFFFFFFD

    # Pad data to sector boundary
    def pad(b: bytes) -> bytes:
        r = len(b) % SECT_SIZE
        return b + b"\x00" * (SECT_SIZE - r) if r else b

    data_padded = pad(data)
    n_data_sectors = len(data_padded) // SECT_SIZE

    # FAT: sector 0 = FAT itself, sector 1 = directory, sectors 2..n+1 = data
    # Total sectors: 1 (FAT) + 1 (dir) + n_data_sectors
    fat = [FATSECT, ENDOFCHAIN]  # sector 0=FAT, sector 1=dir chain ends
    for k in range(n_data_sectors - 1):
        fat.append(2 + k + 1)   # chain: 2->3->...
    fat.append(ENDOFCHAIN)       # last data sector
    # Pad FAT to 512/4 = 128 entries
    while len(fat) % 128 != 0:
        fat.append(FREESECT)
    fat_bytes = struct.pack(f"<{len(fat)}I", *fat)

    # Directory entries (each 128 bytes)
    def dir_entry(name: str, obj_type: int, start: int, size: int,
                  child: int = 0xFFFFFFFF, left: int = 0xFFFFFFFF,
                  right: int = 0xFFFFFFFF) -> bytes:
        enc = name.encode("utf-16-le") if name else b""
        name_len = len(enc) + 2 if enc else 0
        enc = enc.ljust(64, b"\x00")[:64]
        clsid = b"\x00" * 16
        flags = 0
        ts = b"\x00" * 8
        return (
            enc + struct.pack("<H", name_len) + bytes([obj_type, 0]) +
            struct.pack("<III", left, right, child) +
            clsid + struct.pack("<I", flags) +        # StateBits: 4 bytes (no 8)
            ts + ts + struct.pack("<III", start, size, 0)  # StartSector + SizeLow + SizeHigh
        )

    sname = stream_name
    # Dir entry 0: root (type=5, child=1)
    root = dir_entry("Root Entry", 5, 0xFFFFFFFE, 0, child=1)
    # Dir entry 1: our stream (type=2, start=2)
    stream_entry = dir_entry(sname, 2, 2, len(data))
    # Pad directory to 512 bytes (4 entries of 128 bytes each)
    dir_sector = root + stream_entry + b"\x00" * 128 + b"\x00" * 128

    # Header (512 bytes)
    magic = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
    clsid = b"\x00" * 16
    minor_ver = struct.pack("<H", 0x003E)
    major_ver = struct.pack("<H", 0x0003)
    byte_order = b"\xFE\xFF"
    sect_pow = struct.pack("<H", 9)   # 2^9 = 512
    mini_pow = struct.pack("<H", 6)
    reserved = b"\x00" * 6
    num_dir_sects = struct.pack("<I", 0)
    num_fat_sects = struct.pack("<I", 1)
    first_dir_sect = struct.pack("<I", 1)
    txn_sig = struct.pack("<I", 0)
    mini_stream_cutoff = struct.pack("<I", 0x1000)
    first_mini_fat = struct.pack("<I", FREESECT)
    num_mini_fat = struct.pack("<I", 0)
    first_difat = struct.pack("<I", FREESECT)
    num_difat = struct.pack("<I", 0)
    difat = struct.pack("<I", 0) + struct.pack("<I", FREESECT) * 108  # FAT at sector 0
    # Pad difat to 436 bytes (109 entries)
    difat_full = struct.pack("<I", 0) + struct.pack("<I", FREESECT) * 108

    header = (
        magic + clsid + minor_ver + major_ver + byte_order +
        sect_pow + mini_pow + reserved + num_dir_sects + num_fat_sects +
        first_dir_sect + txn_sig + mini_stream_cutoff +
        first_mini_fat + num_mini_fat + first_difat + num_difat +
        difat_full
    )
    assert len(header) == 512, f"Header len = {len(header)}"

    path.write_bytes(header + fat_bytes + dir_sector + data_padded)


def test_ppt_extracts_text_chars(tmp_path):
    p = _build_ppt(tmp_path, ["Diapositiva uno", "Segunda diapositiva"])
    doc = PptExtractor().extract(p)
    assert "Diapositiva uno" in doc.text or "Segunda" in doc.text


def test_ppt_supported_extensions():
    assert ".ppt" in PptExtractor().supported_extensions()


# ---------------------------------------------------------------------------
# Registry smoke test
# ---------------------------------------------------------------------------

def test_registry_resolves_new_formats():
    from app.services.rag.extractors.registry import get_extractor
    for ext in (".rtf", ".epub", ".ppt", ".doc", ".ods", ".odp"):
        result = get_extractor(ext)
        assert result is not None, f"No extractor for {ext}"
