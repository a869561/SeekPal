from app.services.rag.chunking_service import chunk_text
from app.services.rag.types import ExtractedDoc


def test_short_text_one_chunk():
    doc = ExtractedDoc(text="Hola mundo.", extractor="text")
    chunks = chunk_text(doc, chunk_size=100, overlap=20)
    assert len(chunks) == 1
    assert chunks[0].text == "Hola mundo."
    assert chunks[0].chunk_idx == 0
    assert chunks[0].page is None


def test_long_text_splits_with_overlap():
    text = ("Una frase muy larga. " * 200).strip()
    doc = ExtractedDoc(text=text, extractor="text")
    chunks = chunk_text(doc, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    covered = set()
    for c in chunks:
        for i in range(c.offset_start, c.offset_end):
            covered.add(i)
    assert len(covered) >= len(text) * 0.9
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.offset_start < prev.offset_end


def test_assigns_page_from_page_map():
    text = "P1 content.\n\nP2 content extra largo para ocupar espacio."
    page_map = [(1, 0), (2, 13)]
    doc = ExtractedDoc(text=text, page_map=page_map, extractor="pymupdf")
    # chunk_size=3 → max_chars=12 → fuerza split: "P2..." empieza en offset 13 (página 2)
    chunks = chunk_text(doc, chunk_size=3, overlap=0)
    assert chunks[0].page == 1
    assert any(c.page == 2 for c in chunks)


def test_empty_text_returns_empty_list():
    doc = ExtractedDoc(text="", extractor="text")
    assert chunk_text(doc, chunk_size=100, overlap=20) == []


def test_whitespace_only_returns_empty_list():
    doc = ExtractedDoc(text="   \n\n  ", extractor="text")
    assert chunk_text(doc, chunk_size=100, overlap=20) == []


def test_no_page_map_chunks_have_none_page():
    text = "Texto sin mapa de páginas. " * 50
    doc = ExtractedDoc(text=text, extractor="text")
    chunks = chunk_text(doc, chunk_size=20, overlap=5)
    assert all(c.page is None for c in chunks)


def test_offsets_within_text_bounds():
    text = "Contenido de prueba para verificar offsets. " * 30
    doc = ExtractedDoc(text=text, extractor="text")
    chunks = chunk_text(doc, chunk_size=50, overlap=10)
    for c in chunks:
        assert c.offset_start >= 0
        assert c.offset_end <= len(text)
        assert c.offset_start < c.offset_end


def test_chunks_are_non_empty():
    text = "Frase uno.\n\n\n\nFrase dos.\n\n\n\nFrase tres con contenido extra."
    doc = ExtractedDoc(text=text, extractor="text")
    chunks = chunk_text(doc, chunk_size=10, overlap=2)
    assert all(c.text.strip() != "" for c in chunks)


def test_text_without_separators_does_not_crash():
    """Regresión: texto largo sin separadores (base64, JSON minificado, etc.)
    rompía con `ValueError: empty separator` porque el último separador era ""."""
    text = "a" * 3000  # > max_chars (512*4=2048) y sin espacios/newlines
    doc = ExtractedDoc(text=text, extractor="text")
    chunks = chunk_text(doc, chunk_size=512, overlap=64)
    assert len(chunks) >= 2
    assert sum(len(c.text) for c in chunks) >= len(text)


def test_long_token_without_spaces_splits_by_max_chars():
    """Cuando una sola pieza (sin separadores) excede max_chars, se corta."""
    text = "preludio\n\n" + ("z" * 5000) + "\n\nepilogo"
    doc = ExtractedDoc(text=text, extractor="text")
    chunks = chunk_text(doc, chunk_size=512, overlap=0)
    # La 'z'*5000 debe partirse en pedazos <= 2048 chars
    z_chunks = [c for c in chunks if c.text.strip().startswith("z")]
    assert all(len(c.text) <= 2048 for c in z_chunks)
