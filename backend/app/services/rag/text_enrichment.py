"""Enriquecimiento de texto con contexto de ruta para indexación.

Función pura y testeable: construye un string de tokens derivados de la ruta
del fichero relativa a la raíz de la fuente. Estos tokens se añaden al texto
embebido (campo embed_text del Chunk) sin contaminar el snippet ni el payload.

Ejemplos:
  valorant/rangos.png   (root = raíz de la fuente) -> "valorant rangos"
  Fotos/2023/IMG_8472.jpg                           -> "fotos 2023 img 8472"
  grupo_7-8.docx                                    -> "grupo 7 8"
"""

from __future__ import annotations

import re
from pathlib import Path

# Separa camelCase (Word → Word), frontera dígito/letra y letra/dígito.
# Ejemplo: "IMG8472" → ["IMG", "8472"]; "camelCase" → ["camel", "Case"]
_CAMEL_RE = re.compile(
    r"(?<=[a-z])(?=[A-Z])"          # minúscula→mayúscula (camelCase)
    r"|(?<=[A-Z])(?=[A-Z][a-z])"    # secuencia mayúsculas seguida de minúscula
    r"|(?<=\D)(?=\d)"               # no-dígito → dígito
    r"|(?<=\d)(?=\D)"               # dígito → no-dígito
)

# Separadores explícitos: guiones bajos, guiones, espacios y similares.
_SEP_RE = re.compile(r"[_\-\s]+")


def _tokenize_part(part: str) -> list[str]:
    """Descompone una parte de ruta en tokens normalizados.

    Orden de operaciones:
    1. Separar por guiones bajos, guiones y espacios.
    2. Dentro de cada fragmento, separar por camelCase y frontera dígito/letra.
    3. Minúsculas, descartar vacíos.
    """
    tokens: list[str] = []
    for fragment in _SEP_RE.split(part):
        if not fragment:
            continue
        for subtoken in _CAMEL_RE.split(fragment):
            subtoken = subtoken.lower().strip()
            if subtoken:
                tokens.append(subtoken)
    return tokens


def build_path_context(file_path: str, source_root: str | None) -> str:
    """Construye un string de tokens de ruta para enriquecer el embedding.

    Args:
        file_path:   Ruta absoluta (o relativa) del fichero.
        source_root: Carpeta raíz de la fuente indexada. Si es None o si la
                     ruta no es relativa a ella, se usan las últimas 3
                     componentes de la ruta como fallback.

    Returns:
        String de tokens separados por espacio, deduplicados preservando orden.
        Devuelve "" si no se pueden derivar tokens con sentido.

    Ejemplos:
        build_path_context("/src/valorant/rangos.png", "/src") -> "valorant rangos"
        build_path_context("/Fotos/2023/IMG_8472.jpg", "/")    -> "fotos 2023 img 8472"
        build_path_context("/a/b/grupo_7-8.docx", "/a")        -> "b grupo 7 8"
    """
    path = Path(file_path)

    # Calcular ruta relativa a la raíz de la fuente.
    rel: Path | None = None
    if source_root:
        try:
            rel = path.relative_to(source_root)
        except ValueError:
            pass  # ruta fuera del árbol de la fuente → fallback

    if rel is None:
        # Fallback: últimas ~3 componentes (sin incluir el fichero como componente extra)
        parts = path.parts
        # Tomamos hasta 3 carpetas padre + el stem del fichero
        fallback_parts = list(parts[max(0, len(parts) - 4): -1]) + [path.stem]
        rel = Path(*fallback_parts) if fallback_parts else Path(path.stem)

    # Carpetas intermedias + stem del fichero (descartamos la extensión)
    folder_parts = list(rel.parts[:-1])    # carpetas
    stem = rel.stem                        # nombre sin extensión

    # Tokenizar cada parte
    all_tokens: list[str] = []
    for part in folder_parts:
        all_tokens.extend(_tokenize_part(part))
    all_tokens.extend(_tokenize_part(stem))

    # Deduplicar preservando orden de primera aparición
    seen: set[str] = set()
    unique: list[str] = []
    for tok in all_tokens:
        if tok not in seen:
            seen.add(tok)
            unique.append(tok)

    return " ".join(unique)
