"""Escaneo recursivo de fuentes y extracción de metadatos.

El escaneo es asíncrono: los metadatos se calculan en un thread pool para no
bloquear el event loop (la mayoría de extractores son síncronos y de I/O).
Los documentos se vuelcan por lotes a Mongo mediante operaciones bulk upsert.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from beanie import PydanticObjectId
from pymongo import UpdateOne

from app.models.file import FileDoc
from app.models.source import Source
from app.utils import metadata_extractor
from app.utils.mime_classifier import classify, is_indexable


IGNORED_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", ".next",
})
IGNORED_FILES = frozenset({
    "desktop.ini", "thumbs.db", "thumbs.db:encryptable", ".ds_store",
    "ntuser.dat", "ntuser.ini",
})
CONCURRENCY = 8
BULK_BATCH = 200


ProgressCallback = Callable[[int, int, str], Awaitable[None]]


def _is_hidden(name: str) -> bool:
    return name.startswith(".") or name.startswith("$")


def _walk(root: Path) -> list[Path]:
    out: list[Path] = []
    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            continue
        for entry in entries:
            name = entry.name
            if _is_hidden(name):
                continue
            try:
                if entry.is_dir():
                    if name in IGNORED_DIRS:
                        continue
                    stack.append(entry)
                elif entry.is_file():
                    if name.lower() in IGNORED_FILES:
                        continue
                    if is_indexable(entry):
                        out.append(entry)
            except OSError:
                continue
    return out


def _build_doc(source_id: PydanticObjectId, file_path: Path) -> dict | None:
    try:
        stat = file_path.stat()
    except OSError:
        return None
    ext = file_path.suffix.lower()
    category, mime_type = classify(file_path)
    metadata = metadata_extractor.extract(str(file_path), category, ext)
    return {
        "sourceId": source_id,
        "name": file_path.name,
        "path": str(file_path),
        "extension": ext,
        "mimeType": mime_type,
        "category": category,
        "size": stat.st_size,
        "createdAt": datetime.utcfromtimestamp(stat.st_ctime),
        "modifiedAt": datetime.utcfromtimestamp(stat.st_mtime),
        "metadata": metadata,
    }


async def ingest_source(
    source_id: PydanticObjectId,
    on_progress: ProgressCallback,
) -> None:
    source = await Source.get(source_id)
    if source is None:
        raise ValueError("Fuente no encontrada")

    source.status = "scanning"
    await source.save()

    try:
        all_paths = await asyncio.to_thread(_walk, Path(source.path))
        total = len(all_paths)

        await FileDoc.find(FileDoc.sourceId == source_id).delete()

        semaphore = asyncio.Semaphore(CONCURRENCY)
        processed = 0
        ops_buffer: list[UpdateOne] = []

        async def _process_one(file_path: Path):
            async with semaphore:
                return await asyncio.to_thread(_build_doc, source_id, file_path)

        for coro in asyncio.as_completed([_process_one(p) for p in all_paths]):
            doc = await coro
            processed += 1
            if doc is not None:
                ops_buffer.append(
                    UpdateOne(
                        {"sourceId": doc["sourceId"], "path": doc["path"]},
                        {"$set": doc},
                        upsert=True,
                    )
                )
                await on_progress(processed, total, Path(doc["path"]).name)
            else:
                await on_progress(processed, total, "")

            if len(ops_buffer) >= BULK_BATCH:
                await FileDoc.get_pymongo_collection().bulk_write(ops_buffer, ordered=False)
                ops_buffer.clear()

        if ops_buffer:
            await FileDoc.get_pymongo_collection().bulk_write(ops_buffer, ordered=False)

        try:
            await _index_text_documents(source_id, on_progress=on_progress)
        except Exception as exc:
            print(f"[seekpal] RAG indexing failed for source {source_id}: {exc}")

        # Guard: source may have been deleted while ingestion was running
        if await Source.get(source_id) is None:
            await FileDoc.find(FileDoc.sourceId == source_id).delete()
            return

        file_count = await FileDoc.find(FileDoc.sourceId == source_id).count()
        source.status = "done"
        source.lastIngested = datetime.utcnow()
        source.fileCount = file_count
        await source.save()
    except Exception:
        if await Source.get(source_id) is not None:
            source.status = "error"
            await source.save()
        raise


async def _index_text_documents(
    source_id: PydanticObjectId,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Lanza indexación RAG para cada FileDoc de categoría text/document."""
    from beanie.operators import In

    from app.core.database import get_index_service
    from app.models.file import RagMetadata

    try:
        index_service = get_index_service()
    except RuntimeError:
        return

    query = FileDoc.find(
        FileDoc.sourceId == source_id,
        In(FileDoc.category, ["text", "document"]),
    )
    total = await query.count()
    indexed = 0

    # Signal start of indexing phase with total = -1 as sentinel
    if on_progress:
        await on_progress(0, -total, "")

    async for file_doc in query:
        result = await index_service.index_file(
            file_id=str(file_doc.id),
            source_id=str(file_doc.sourceId),
            file_name=file_doc.name,
            category=file_doc.category,
            extension=file_doc.extension,
            path=Path(file_doc.path),
        )
        file_doc.metadata.rag = RagMetadata(
            indexStatus=result.status,
            indexedChunks=result.chunks,
            lastIndexedAt=result.indexed_at,
            extractor=result.extractor,
            error=result.error,
        )
        await file_doc.save()
        indexed += 1
        if on_progress:
            await on_progress(indexed, -total, file_doc.name)
