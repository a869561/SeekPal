"""Extractor para hojas de cálculo Excel (.xlsx, .xls).

Estrategia:
- Lee todas las hojas visibles de izquierda a derecha.
- Cada hoja se convierte en texto tabular: celdas separadas por tabulador,
  filas por salto de línea. Las filas completamente vacías se omiten.
- El nombre de cada hoja se incluye como cabecera para facilitar la recuperación.
"""
from __future__ import annotations

from pathlib import Path

import openpyxl

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc


class XlsxExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        sections: list[str] = []

        for sheet in wb.worksheets:
            rows: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                line = "\t".join(cells).rstrip()
                if line.strip():
                    rows.append(line)
            if rows:
                sections.append(f"[{sheet.title}]\n" + "\n".join(rows))

        wb.close()
        text = "\n\n".join(sections)
        return ExtractedDoc(text=text, page_map=[], extractor="xlsx")

    def supported_extensions(self) -> list[str]:
        return [".xlsx", ".xls"]
