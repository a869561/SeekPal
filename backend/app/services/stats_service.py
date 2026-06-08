from beanie import PydanticObjectId

from app.models.file import FileDoc
from app.models.source import Source


async def get_summary() -> dict:
    files_col = FileDoc.get_pymongo_collection()

    total_files = await files_col.count_documents({})

    total_size_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$size"}}}]
    total_size_cur = await files_col.aggregate(total_size_pipeline).to_list(length=1)
    total_size = total_size_cur[0]["total"] if total_size_cur else 0

    by_category_pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}, "size": {"$sum": "$size"}}},
        {"$sort": {"count": -1}},
    ]
    by_category = await files_col.aggregate(by_category_pipeline).to_list(length=None)

    active_sources = await Source.find(Source.status == "done").count()

    last_indexed_pipeline = [
        {"$group": {"_id": None, "last": {"$max": "$metadata.rag.lastIndexedAt"}}}
    ]
    last_indexed_cur = await files_col.aggregate(last_indexed_pipeline).to_list(length=1)
    last_indexed_raw = last_indexed_cur[0]["last"] if last_indexed_cur else None
    last_indexed = last_indexed_raw.isoformat() if last_indexed_raw is not None else None

    return {
        "totalFiles": total_files,
        "totalSize": total_size,
        "activeSources": active_sources,
        "byCategory": by_category,
        "lastIndexed": last_indexed,
    }


ALLOWED_SORT = frozenset({"name", "size", "modifiedAt", "createdAt"})


async def get_files(
    source_id: str | None,
    category: str | None,
    page: int,
    limit: int,
    sort_by: str,
    sort_dir: str,
) -> dict:
    filter_query: dict = {}
    if source_id:
        filter_query["sourceId"] = PydanticObjectId(source_id)
    if category:
        filter_query["category"] = category

    sort_field = sort_by if sort_by in ALLOWED_SORT else "size"
    direction = 1 if sort_dir == "asc" else -1

    skip = (page - 1) * limit
    files_col = FileDoc.get_pymongo_collection()

    cursor = files_col.find(filter_query).sort(sort_field, direction).skip(skip).limit(limit)
    files = await cursor.to_list(length=limit)
    total = await files_col.count_documents(filter_query)

    return {
        "files": files,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if total else 1,
    }
