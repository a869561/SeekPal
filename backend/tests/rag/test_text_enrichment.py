"""Tests para build_path_context (text_enrichment.py).

Cubre: ruta normal relativa, deduplicación de tokens, nombre de cámara con
carpetas con sentido, y fallback cuando la ruta no es relativa a source_root.
"""

import pytest

from app.services.rag.text_enrichment import build_path_context


# ---------------------------------------------------------------------------
# Ruta normal relativa a source_root
# ---------------------------------------------------------------------------

def test_simple_relative_path():
    """valorant/rangos.png relativo a /src -> 'valorant rangos'."""
    result = build_path_context("/src/valorant/rangos.png", "/src")
    assert result == "valorant rangos"


def test_nested_path():
    """Carpetas anidadas: proyectos/TFG/propuesta.pdf -> 'proyectos tfg propuesta'."""
    result = build_path_context("/datos/proyectos/TFG/propuesta.pdf", "/datos")
    assert result == "proyectos tfg propuesta"


# ---------------------------------------------------------------------------
# Deduplicación: token repetido en carpeta y nombre del fichero
# ---------------------------------------------------------------------------

def test_dedupe_repeated_token():
    """Si el mismo token aparece en la carpeta y en el stem, solo aparece una vez."""
    # Carpeta "valorant" + stem "valorant_rangos" → tokens: valorant, valorant, rangos
    # Tras dedup: "valorant rangos"
    result = build_path_context("/src/valorant/valorant_rangos.png", "/src")
    assert result == "valorant rangos"


def test_dedupe_camelcase_and_folder():
    """Carpeta 'img' + stem 'imgPreview' → dedup de 'img'."""
    result = build_path_context("/root/img/imgPreview.jpg", "/root")
    # Tokens de carpeta: img; tokens de stem: img, preview → dedup: img preview
    assert result == "img preview"


# ---------------------------------------------------------------------------
# Nombre de cámara (IMG_XXXX) con carpetas significativas
# ---------------------------------------------------------------------------

def test_camera_filename_with_meaningful_folders():
    """Fotos/2023/IMG_8472.jpg -> 'fotos 2023 img 8472'."""
    result = build_path_context("/almacen/Fotos/2023/IMG_8472.jpg", "/almacen")
    assert result == "fotos 2023 img 8472"


def test_underscore_and_dash_in_stem():
    """grupo_7-8.docx -> tokens 'grupo 7 8'."""
    result = build_path_context("/datos/grupo_7-8.docx", "/datos")
    assert result == "grupo 7 8"


# ---------------------------------------------------------------------------
# Fallback: ruta no relativa a source_root
# ---------------------------------------------------------------------------

def test_fallback_when_not_relative():
    """Si la ruta no está bajo source_root, se usan las últimas ~3 componentes."""
    result = build_path_context("/other/tree/deep/folder/rangos.png", "/src")
    # Fallback: últimas 3 carpetas + stem => deep, folder, rangos (o similar)
    # Lo importante: no lanza excepción y devuelve algo con sentido
    assert "rangos" in result
    assert isinstance(result, str)


def test_fallback_no_source_root():
    """source_root=None -> fallback a últimas componentes."""
    result = build_path_context("/datos/proyectos/TFG/propuesta.pdf", None)
    assert "propuesta" in result
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Casos borde
# ---------------------------------------------------------------------------

def test_single_file_at_root():
    """Fichero directamente en la raíz de la fuente: solo el stem."""
    result = build_path_context("/src/documento.txt", "/src")
    assert result == "documento"


def test_camelcase_stem():
    """CamelCase en el nombre del fichero se separa correctamente."""
    result = build_path_context("/src/myProjectDocs.docx", "/src")
    # "myProjectDocs" -> my, project, docs
    assert result == "my project docs"


def test_mixed_numbers_and_letters():
    """Frontera dígito/letra: 'Fotos2023' -> 'fotos 2023'."""
    result = build_path_context("/src/Fotos2023.jpg", "/src")
    assert result == "fotos 2023"
