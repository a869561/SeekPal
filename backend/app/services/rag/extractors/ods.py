"""Extractor para hojas de cálculo OpenDocument (.ods).

Usa odfpy (ya instalado para OdtExtractor).
Mismo formato de salida que XlsxExtractor: cabecera de hoja + filas tabuladas.
"""
from __future__ import annotations

from pathlib import Path

from odf.opendocument import load
from odf.table import Table, TableCell, TableRow
from odf.text import P

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc


def _cell_text(cell: TableCell) -> str:
    """Extrae el texto plano de una celda ODS."""
    parts = []
    for p in cell.getElementsByType(P):
        line = "".join(
            node.data for node in p.childNodes if hasattr(node, "data")
        )
        parts.append(line)
    return " ".join(parts).strip()


class OdsExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        doc = load(str(path))
        sections: list[str] = []

        for sheet in doc.spreadsheet.getElementsByType(Table):
            name = sheet.getAttribute("name") or "Hoja"
            rows: list[str] = []
            for row in sheet.getElementsByType(TableRow):
                cells = [_cell_text(c) for c in row.getElementsByType(TableCell)]
                line = "\t".join(cells).rstrip()
                if line.strip():
                    rows.append(line)
            if rows:
                sections.append(f"[{name}]\n" + "\n".join(rows))

        text = "\n\n".join(sections)
        return ExtractedDoc(text=text, page_map=[], extractor="ods")

    def supported_extensions(self) -> list[str]:
        return [".ods"]
