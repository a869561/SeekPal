"""Tests de extracción de contenido contra el corpus de evaluación.

Verifica que cada extractor:
  1. Devuelve texto no vacío para el fichero de su formato.
  2. Contiene hechos específicos del contenido de build_corpus.py.

Si el corpus no existe, genera los ficheros automáticamente.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Localización del corpus
# ---------------------------------------------------------------------------

CORPUS = Path(__file__).parent.parent / "eval" / "corpus"
BACKEND = Path(__file__).parent.parent.parent  # backend/


def _ensure_corpus() -> None:
    """Genera el corpus si no existe o está vacío."""
    if CORPUS.exists() and any(CORPUS.iterdir()):
        return
    import subprocess, sys
    script = BACKEND / "tests" / "eval" / "build_corpus.py"
    subprocess.run([sys.executable, str(script)], check=True, cwd=str(BACKEND))


def _extract(filename: str):
    """Resuelve extractor y extrae texto del fichero del corpus."""
    from app.services.rag.extractors.registry import get_extractor

    path = CORPUS / filename
    if not path.exists():
        pytest.skip(f"Corpus file not found: {filename}")
    extractor = get_extractor(path.suffix, path=path)
    assert extractor is not None, f"Sin extractor para '{path.suffix}'"
    return extractor.extract(path)


# Asegurar corpus disponible al importar el módulo (una sola vez)
try:
    _ensure_corpus()
except Exception:
    pass  # si falla, los tests individuales harán skip


# ══════════════════════════════════════════════════════════════════════════
# 1. TXT — sistema_solar.txt
# ══════════════════════════════════════════════════════════════════════════

def test_txt_sistema_solar():
    doc = _extract("sistema_solar.txt")
    text = doc.text
    assert doc.extractor in ("text", "txt")
    assert len(text) > 200
    assert "99,86" in text            # % de masa del Sol
    assert "4600" in text             # millones de años
    assert "Mercurio" in text         # primer planeta terrestre
    assert "Neptuno" in text          # último planeta


# ══════════════════════════════════════════════════════════════════════════
# 2. MD — python_lenguaje.md
# ══════════════════════════════════════════════════════════════════════════

def test_md_python():
    doc = _extract("python_lenguaje.md")
    text = doc.text
    assert doc.extractor in ("text", "txt")
    assert len(text) > 200
    assert "Guido van Rossum" in text  # creador
    assert "1991" in text              # año de publicación
    assert "Monty Python" in text      # origen del nombre


# ══════════════════════════════════════════════════════════════════════════
# 3. PDF — cambio_climatico.pdf
# ══════════════════════════════════════════════════════════════════════════

def test_pdf_cambio_climatico():
    doc = _extract("cambio_climatico.pdf")
    text = doc.text
    assert doc.extractor == "pdf"
    assert len(text) > 100
    assert "420" in text               # ppm CO2 en 2023
    assert "196" in text               # países Acuerdo de París
    assert "2015" in text              # año del acuerdo


# ══════════════════════════════════════════════════════════════════════════
# 4. DOCX — inteligencia_artificial.docx
# ══════════════════════════════════════════════════════════════════════════

def test_docx_inteligencia_artificial():
    doc = _extract("inteligencia_artificial.docx")
    text = doc.text
    assert doc.extractor == "docx"
    assert len(text) > 100
    assert "Dartmouth" in text         # conferencia fundacional de la IA
    assert "Deep Blue" in text         # IBM vs Kasparov 1997
    assert "ChatGPT" in text           # OpenAI 2022


# ══════════════════════════════════════════════════════════════════════════
# 5. PPTX — historia_internet.pptx
# ══════════════════════════════════════════════════════════════════════════

def test_pptx_historia_internet():
    doc = _extract("historia_internet.pptx")
    text = doc.text
    assert doc.extractor == "pptx"
    assert len(text) > 100
    assert "ARPANET" in text
    assert "Tim Berners-Lee" in text
    assert "HTML" in text


# ══════════════════════════════════════════════════════════════════════════
# 6. XLSX — energias_renovables.xlsx
# ══════════════════════════════════════════════════════════════════════════

def test_xlsx_energias_renovables():
    doc = _extract("energias_renovables.xlsx")
    text = doc.text
    assert doc.extractor == "xlsx"
    assert len(text) > 30
    assert "Solar" in text             # energía solar fotovoltaica
    assert "1177" in text              # GW instalados solar en 2023


# ══════════════════════════════════════════════════════════════════════════
# 7. ODT — biologia_celular.odt
# ══════════════════════════════════════════════════════════════════════════

def test_odt_biologia_celular():
    doc = _extract("biologia_celular.odt")
    text = doc.text
    assert doc.extractor == "odt"
    assert len(text) > 100
    assert "Virchow" in text           # principio de la célula
    assert "ADN" in text               # molécula genética
    assert "mitosis" in text           # división celular


# ══════════════════════════════════════════════════════════════════════════
# 8. ODS — tabla_periodica.ods
# ══════════════════════════════════════════════════════════════════════════

def test_ods_tabla_periodica():
    doc = _extract("tabla_periodica.ods")
    text = doc.text
    assert doc.extractor == "ods"
    assert len(text) > 30
    assert "Au" in text                # símbolo del oro
    assert "79" in text                # número atómico del oro
    assert "H" in text                 # hidrógeno (H)


# ══════════════════════════════════════════════════════════════════════════
# 9. ODP — sistema_nervioso.odp
# ══════════════════════════════════════════════════════════════════════════

def test_odp_sistema_nervioso():
    doc = _extract("sistema_nervioso.odp")
    text = doc.text
    assert doc.extractor == "odp"
    assert len(text) > 50
    assert "sinapsis" in text          # comunicación neuronal
    assert "86" in text               # ~86 000 millones de neuronas
    # médula puede perder acento según el extractor
    assert "médula" in text or "medula" in text.lower()


# ══════════════════════════════════════════════════════════════════════════
# 10. RTF — historia_fisica.rtf
# ══════════════════════════════════════════════════════════════════════════

def test_rtf_historia_fisica():
    doc = _extract("historia_fisica.rtf")
    text = doc.text
    assert doc.extractor == "rtf"
    assert len(text) > 100
    assert "Newton" in text            # mecánica clásica
    assert "Einstein" in text          # relatividad
    assert "Higgs" in text             # bosón descubierto en CERN 2012


# ══════════════════════════════════════════════════════════════════════════
# 11. EPUB — historia_computacion.epub
# ══════════════════════════════════════════════════════════════════════════

def test_epub_historia_computacion():
    doc = _extract("historia_computacion.epub")
    text = doc.text
    assert doc.extractor == "epub"
    assert len(text) > 100
    assert "Turing" in text            # Alan Turing
    assert "ENIAC" in text             # primer computador electrónico
    # El corpus escribe "17 468" con espacio ordinario
    assert "17" in text and "468" in text


# ══════════════════════════════════════════════════════════════════════════
# 12. DOC — economia_basica.doc
# ══════════════════════════════════════════════════════════════════════════

def test_doc_economia_basica():
    doc = _extract("economia_basica.doc")
    text = doc.text
    assert doc.extractor == "doc"
    assert len(text) > 100
    assert "Bretton Woods" in text     # fundación FMI y Banco Mundial (1944)
    assert "PIB" in text               # Producto Interior Bruto
    # inflación puede llevar o no tilde según la decodificación
    assert "inflaci" in text.lower()


# ══════════════════════════════════════════════════════════════════════════
# 13. PPT — astronomia.ppt
# ══════════════════════════════════════════════════════════════════════════

def test_ppt_astronomia():
    doc = _extract("astronomia.ppt")
    text = doc.text
    assert doc.extractor == "ppt"
    assert len(text) > 50
    assert "Big Bang" in text          # teoría del origen del universo
    assert "13800" in text             # millones de años del universo
    # La vía láctea puede no tener tildes en el corpus PPT (ASCII puro)
    assert "Lactea" in text or "láctea" in text.lower() or "Via" in text


# ══════════════════════════════════════════════════════════════════════════
# Smoke test: todos los ficheros → texto no vacío
# ══════════════════════════════════════════════════════════════════════════

def test_all_corpus_files_non_empty():
    """Smoke test: todos los ficheros del corpus extraen texto no vacío."""
    from app.services.rag.extractors.registry import get_extractor

    if not CORPUS.exists():
        pytest.skip("Corpus directory does not exist")

    failures: list[str] = []
    for path in sorted(CORPUS.iterdir()):
        if path.suffix == "":
            continue
        extractor = get_extractor(path.suffix, path=path)
        if extractor is None:
            failures.append(f"{path.name}: sin extractor para '{path.suffix}'")
            continue
        try:
            doc = extractor.extract(path)
            if not doc.text or not doc.text.strip():
                failures.append(f"{path.name}: texto vacío")
        except Exception as exc:
            failures.append(f"{path.name}: excepción — {exc}")

    if failures:
        pytest.fail("Extractores con problemas:\n" + "\n".join(failures))
