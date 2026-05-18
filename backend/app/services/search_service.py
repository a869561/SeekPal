import re

from beanie import PydanticObjectId

from app.models.file import FileDoc


_SPECIAL_REGEX = re.compile(r"[.*+?^${}()|\[\]\\]")


def _build_query(q: str | None, category: str | None, source_id: str | None) -> dict:
    filter_query: dict = {}
    if q and q.strip():
        words = [_SPECIAL_REGEX.sub(lambda m: f"\\{m.group(0)}", w) for w in q.strip().split()]
        pattern = "|".join(w for w in words if w)
        if pattern:
            regex = {"$regex": pattern, "$options": "i"}
            filter_query["$or"] = [{"name": regex}, {"path": regex}]
    if category:
        filter_query["category"] = category
    if source_id:
        filter_query["sourceId"] = PydanticObjectId(source_id)
    return filter_query


async def search(
    q: str | None,
    category: str | None,
    source_id: str | None,
    page: int,
    limit: int,
) -> dict:
    filter_query = _build_query(q, category, source_id)
    skip = (page - 1) * limit
    files_col = FileDoc.get_pymongo_collection()

    cursor = files_col.find(filter_query).sort("name", 1).skip(skip).limit(limit)
    files = await cursor.to_list(length=limit)
    total = await files_col.count_documents(filter_query)

    return {
        "files": files,
        "total": total,
        "page": page,
        "pages": max((total + limit - 1) // limit, 1),
    }
