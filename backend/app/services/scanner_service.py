"""Escaneo recursivo de fuentes y extracción de metadatos.

El escaneo es asíncrono: los metadatos se calculan en un thread pool para no
bloquear el event loop (la mayoría de extractores son síncronos y de I/O).
Los documentos se vuelcan por lotes a Mongo mediante operaciones bulk upsert.
"""

import asyncio
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Awaitable, Callable

from beanie import PydanticObjectId
from pymongo import UpdateOne

from app.models.file import FileDoc
from app.models.source import Source
from app.utils import metadata_extractor
from app.utils.mime_classifier import classify, is_indexable

logger = logging.getLogger("seekpal.scanner")


IGNORED_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", ".next",
})
IGNORED_FILES = frozenset({
    "desktop.ini", "thumbs.db", "thumbs.db:encryptable", ".ds_store",
    "ntuser.dat", "ntuser.ini",
})
CONCURRENCY = 8
BULK_BATCH = 200
_INDEX_GROUP = 15   # ficheros por grupo


def _chunk_batch_size() -> int:
    """Lee el tamano de lote de embedding desde settings (BGE-M3 en CPU: ~8)."""
    from app.core.config import settings
    return max(1, settings.rag_embed_batch)


ProgressCallback = Callable[[int, int, str], Awaitable[None]]

# --- Pause/resume state per source ---
_pause_events: dict[str, asyncio.Event] = {}


def _pause_event(source_id: str) -> asyncio.Event:
    ev = _pause_events.get(source_id)
    if ev is None:
        ev = asyncio.Event()
        ev.set()
        _pause_events[source_id] = ev
    return ev


def pause_ingest(source_id: str) -> None:
    _pause_event(source_id).clear()


def resume_ingest(source_id: str) -> None:
    _pause_event(source_id).set()


def cleanup_ingest(source_id: str) -> None:
    _pause_events.pop(source_id, None)


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
        "createdAt": datetime.fromtimestamp(stat.st_ctime, UTC),
        "modifiedAt": datetime.fromtimestamp(stat.st_mtime, UTC),
        "metadata": metadata,
    }


async def ingest_source(
    source_id: PydanticObjectId,
    on_progress: ProgressCallback,
) -> None:
    source = await Source.get(source_id)
    if source is None:
        raise ValueError("Fuente no encontrada")

    src_label = f"{source.name}"
    source.status = "scanning"
    await source.save()

    t_ingest_start = time.perf_counter()
    logger.info("[%s] Iniciando ingesta: %s", src_label, source.path)

    try:
        all_paths = await asyncio.to_thread(_walk, Path(source.path))
        total = len(all_paths)
        logger.info("[%s] Encontrados %d ficheros indexables", src_label, total)

        # Purga la indexacion anterior antes de reingestar. Los FileDoc se
        # recrean con un _id nuevo en cada ingesta, y como el chunk_id de Qdrant
        # deriva de ese _id, los vectores del intento previo quedarian huerfanos
        # (mismo source_id, file_id viejo) y seguirian apareciendo en busquedas.
        # Borrar por source_id deja Qdrant limpio para esta fuente.
        try:
            from app.core.database import get_vector_service
            vector = get_vector_service()
            await asyncio.to_thread(vector.delete_by_source, str(source_id))
        except Exception as exc:
            logger.warning("[%s] No se pudieron purgar vectores previos: %s", src_label, exc)

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

        rag_stats: dict[str, int] | None = None
        try:
            rag_stats = await _index_text_documents(source_id, src_label=src_label, on_progress=on_progress)
        except Exception as exc:
            logger.error("[%s] RAG indexing fallido: %s", src_label, exc)

        # Guard: source may have been deleted while ingestion was running
        if await Source.get(source_id) is None:
            await FileDoc.find(FileDoc.sourceId == source_id).delete()
            return

        file_count = await FileDoc.find(FileDoc.sourceId == source_id).count()
        source.status = "done"
        source.lastIngested = datetime.now(UTC)
        source.fileCount = file_count
        if rag_stats is not None:
            source.indexedCount = rag_stats["indexed"]
            source.skippedCount = rag_stats["skipped"]
            source.failedCount = rag_stats["failed"]
        await source.save()

        elapsed = time.perf_counter() - t_ingest_start
        m, s = divmod(int(elapsed), 60)
        logger.info("[%s] Ingesta finalizada: %d ficheros totales — %dm %ds",
                    src_label, file_count, m, s)
    except Exception:
        if await Source.get(source_id) is not None:
            source.status = "error"
            await source.save()
        logger.error("[%s] Ingesta terminada con error", src_label)
        raise


async def _index_text_documents(
    source_id: PydanticObjectId,
    src_label: str = "",
    on_progress: ProgressCallback | None = None,
) -> dict[str, int]:
    """Indexación RAG en grupos de _INDEX_GROUP ficheros.

    Cada grupo pasa por tres fases: extracción+chunking en paralelo,
    embedding batch y guardado en Qdrant+MongoDB. Emitir progreso entre
    grupos permite al usuario ver avance cada ~40 ficheros y habilita
    el punto de pausa entre grupos.

    Categorías indexadas: text + document (extracción directa) y
    image/audio/video (extracción multimedia via Whisper / RapidOCR /
    Moondream del perfil MVP). El nombre de la función se mantiene por
    compatibilidad histórica aunque ya cubre todos los tipos indexables.
    """
    from beanie.operators import In

    from app.core.database import get_index_service
    from app.models.file import RagMetadata

    try:
        index_service = get_index_service()
    except RuntimeError:
        logger.warning("RAG indexing saltado: IndexService no inicializado (source %s)", source_id)
        return {"indexed": 0, "skipped": 0, "failed": 0, "chunks": 0}

    # Master switch: si el usuario desactiva multimedia desde Settings,
    # solo indexamos texto/documento. Los ficheros multimedia ya indexados
    # permanecen en Qdrant hasta el siguiente borrado de fuente.
    from app.core import runtime_settings
    categories = ["text", "document"]
    if runtime_settings.get("indexMultimedia", True):
        categories.extend(["image", "audio", "video"])

    query = FileDoc.find(
        FileDoc.sourceId == source_id,
        In(FileDoc.category, categories),
    )
    files = await query.to_list()
    total = len(files)
    if not files:
        return {"indexed": 0, "skipped": 0, "failed": 0, "chunks": 0}

    src_str = str(source_id)
    from app.services.rag.index_service import PreparedFile

    semaphore = asyncio.Semaphore(CONCURRENCY)
    # text/document son fast-path; multimedia requiere mucho mas tiempo:
    # transcripcion de audio ~real-time, video aun mas (audio + N captions).
    # Si useDocling esta activo, los PDF tambien son lentos (~3-10s/pag).
    _EXTRACT_TIMEOUT_TEXT = 45.0
    _EXTRACT_TIMEOUT_PDF_DOCLING = 1800.0  # 30 min/PDF con Docling
    _EXTRACT_TIMEOUT_AUDIO = 600.0   # 10 min/audio
    _EXTRACT_TIMEOUT_IMAGE = 120.0   # 2 min/imagen (OCR + caption Moondream)
    _EXTRACT_TIMEOUT_VIDEO = 1800.0  # 30 min/video

    from app.core import runtime_settings as _rs
    _use_docling = bool(_rs.get("useDocling", False))

    def _timeout_for(cat: str, ext: str) -> float:
        if cat == "audio": return _EXTRACT_TIMEOUT_AUDIO
        if cat == "image": return _EXTRACT_TIMEOUT_IMAGE
        if cat == "video": return _EXTRACT_TIMEOUT_VIDEO
        if cat == "document" and ext == ".pdf" and _use_docling:
            return _EXTRACT_TIMEOUT_PDF_DOCLING
        return _EXTRACT_TIMEOUT_TEXT

    async def _prepare(file_doc):
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    index_service.prepare_file(
                        file_id=str(file_doc.id),
                        source_id=str(file_doc.sourceId),
                        file_name=file_doc.name,
                        category=file_doc.category,
                        extension=file_doc.extension,
                        path=Path(file_doc.path),
                    ),
                    timeout=_timeout_for(file_doc.category, file_doc.extension),
                )
            except asyncio.TimeoutError:
                return PreparedFile(
                    str(file_doc.id), str(file_doc.sourceId), file_doc.name,
                    file_doc.category, file_doc.extension,
                    error="extraction timeout",
                )
            except Exception as exc:
                return PreparedFile(
                    str(file_doc.id), str(file_doc.sourceId), file_doc.name,
                    file_doc.category, file_doc.extension,
                    error=f"preparation error: {exc}",
                )

    indexed = 0    # ficheros ya almacenados en Qdrant (avanza en fase 3)
    extracted = 0  # ficheros ya extraídos (avanza en fase 1, cumulative entre grupos)

    # Contadores globales para el resumen final
    cnt_indexed = 0
    cnt_skipped = 0
    cnt_failed  = 0
    cnt_chunks  = 0
    t_rag_start = time.perf_counter()

    logger.info("[%s] RAG: %d ficheros a indexar", src_label, total)

    for group_start in range(0, total, _INDEX_GROUP):
        group = files[group_start : group_start + _INDEX_GROUP]
        group_end = min(group_start + _INDEX_GROUP, total)
        t_group = time.perf_counter()
        logger.info(
            "[%s] Grupo %d–%d / %d: extrayendo %d ficheros...",
            src_label, group_start + 1, group_end, total, len(group),
        )

        # Punto de pausa entre grupos
        await _pause_event(src_str).wait()

        # Fase 1 — extracción + chunking en paralelo con progreso por fichero
        prepared_group: list = [None] * len(group)

        async def _prepare_tracked(fd, idx, _grp=prepared_group):
            nonlocal extracted
            if on_progress:
                await on_progress(extracted, -total, f"__extract__:{fd.name}")
            t0 = time.perf_counter()
            result = await _prepare(fd)
            dt = time.perf_counter() - t0
            _grp[idx] = result
            extracted += 1
            if result is not None and not result.skipped:
                logger.info("[%s]   ✓ %s — %d chunks (%.1fs)",
                            src_label, fd.name, len(result.chunks), dt)
            elif result is not None and result.error:
                logger.warning("[%s]   ✗ %s — %s (%.1fs)",
                               src_label, fd.name, result.error, dt)
            else:
                logger.info("[%s]   · %s — vacío/sin texto (%.1fs)",
                            src_label, fd.name, dt)
            if on_progress:
                await on_progress(extracted, -total, f"__extract__:{fd.name}")
            return result

        await asyncio.gather(*[_prepare_tracked(fd, i) for i, fd in enumerate(group)])

        # Fase 2 — embedding (dense + sparse) en lotes de CHUNK_BATCH con progreso por lote
        all_texts: list[str] = [
            chunk.text
            for prep in prepared_group
            if prep is not None and not prep.skipped
            for chunk in prep.chunks
        ]
        all_vectors: list = []         # dense (float[] | None)
        all_sparse_vectors: list = []  # sparse (SparseVector)
        total_chunks = len(all_texts)

        if total_chunks > 0:
            logger.info(
                "[%s] Embedding %d chunks del grupo %d–%d...",
                src_label, total_chunks, group_start + 1, group_end,
            )
            if on_progress:
                # Marca el cambio de fase extracting → embedding para el frontend
                await on_progress(0, -total, "__embedding__")
                await on_progress(0, -total, f"__embed_progress__:0/{total_chunks}")
            batch_size = _chunk_batch_size()
            for chunk_start in range(0, total_chunks, batch_size):
                sub_batch = all_texts[chunk_start : chunk_start + batch_size]
                try:
                    sub_vecs, sub_sparse = await asyncio.gather(
                        asyncio.wait_for(
                            index_service.embed_batch(sub_batch),
                            timeout=120.0,  # 2 min por lote de chunks
                        ),
                        index_service.embed_sparse_batch(sub_batch),
                    )
                except asyncio.TimeoutError:
                    logger.warning("embed timeout lote %d-%d", chunk_start, chunk_start + len(sub_batch))
                    sub_vecs = [None] * len(sub_batch)
                    sub_sparse = await index_service.embed_sparse_batch(sub_batch)
                all_vectors.extend(sub_vecs)
                all_sparse_vectors.extend(sub_sparse)
                chunks_done = min(chunk_start + batch_size, total_chunks)
                if on_progress:
                    await on_progress(0, -total, f"__embed_progress__:{chunks_done}/{total_chunks}")

        # Guard: abort if source was deleted during extraction/embedding
        if await Source.get(source_id) is None:
            cleanup_ingest(src_str)
            return {"indexed": cnt_indexed, "skipped": cnt_skipped,
                    "failed": cnt_failed, "chunks": cnt_chunks}

        # Phase 3: store in Qdrant + update MongoDB, emit progress per file
        logger.info(
            "[%s] Guardando grupo %d–%d en Qdrant (%d ficheros)...",
            src_label, group_start + 1, group_end, len(group),
        )
        vec_idx = 0
        for file_doc, prep in zip(group, prepared_group):
            if prep is None:
                cnt_failed += 1
                indexed += 1
                if on_progress:
                    await on_progress(indexed, -total, file_doc.name)
                continue
            if prep.skipped:
                status = "skipped" if prep.error in (
                    "skipped", "empty text", "no chunks produced", None
                ) else "failed"
                if status == "failed":
                    cnt_failed += 1
                else:
                    cnt_skipped += 1
                rag = RagMetadata(indexStatus=status, indexedChunks=0,
                                  extractor=prep.extractor, error=prep.error)
            else:
                n = len(prep.chunks)
                file_vectors = all_vectors[vec_idx : vec_idx + n]
                file_sparse = all_sparse_vectors[vec_idx : vec_idx + n]
                vec_idx += n
                result = await index_service.store_prepared(prep, file_vectors, file_sparse)
                rag = RagMetadata(
                    indexStatus=result.status,
                    indexedChunks=result.chunks,
                    lastIndexedAt=result.indexed_at,
                    extractor=result.extractor,
                    error=result.error,
                )
                if result.status == "done":
                    cnt_indexed += 1
                    cnt_chunks += result.chunks
                else:
                    cnt_failed += 1

            file_doc.metadata.rag = rag
            await file_doc.save()
            indexed += 1
            if on_progress:
                await on_progress(indexed, -total, file_doc.name)

    cleanup_ingest(src_str)

    dt_rag = time.perf_counter() - t_rag_start
    m_rag, s_rag = divmod(int(dt_rag), 60)
    logger.info("[%s] ─────────────────────────────────────────────────────────────", src_label)
    logger.info(
        "[%s] RAG completado: %d indexados · %d vacíos · %d errores · %d chunks — %dm %ds",
        src_label, cnt_indexed, cnt_skipped, cnt_failed, cnt_chunks, m_rag, s_rag,
    )
    return {"indexed": cnt_indexed, "skipped": cnt_skipped,
            "failed": cnt_failed, "chunks": cnt_chunks}
