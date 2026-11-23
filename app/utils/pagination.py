class Pagination:
    def __init__(self, page: int = 1, page_size: int = 25):
        self.page = max(1, page)
        self.page_size = min(100, max(1, page_size))
        self.skip = (self.page - 1) * self.page_size

class ListInput:
    def __init__(self, q: str = "", sort: str = "", dir: str = "asc", page: int = 1, page_size: int = 25, filters: dict = None):
        self.q = q
        self.sort = sort
        self.dir = dir
        self.page = page
        self.page_size = page_size
        self.filters = filters or {}

class ListResponse:
    def __init__(self, rows: list, total: int, facet_counts: dict = None):
        self.rows = rows
        self.total = total
        self.facet_counts = facet_counts or {}

def list_input_validator(q: str = "", sort: str = "", dir: str = "asc", page: int = 1, page_size: int = 25, filters: dict = None):
    return ListInput(q=q, sort=sort, dir=dir, page=page, page_size=page_size, filters=filters)

def build_list_response(rows, total, facet_counts=None):
    return {"rows": rows, "total": total, "facetCounts": facet_counts or {}}


def apply_list(stmt, model, input, search_fields=()):
    """Apply q, filters, sort and pagination to a SQLAlchemy select."""
    from sqlalchemy import or_

    if input.q and search_fields:
        clauses = [getattr(model, field).ilike(f"%{input.q}%") for field in search_fields if hasattr(model, field)]
        if clauses:
            stmt = stmt.where(or_(*clauses))
    for key, value in (input.filters or {}).items():
        if value in (None, "", []):
            continue
        column = getattr(model, key, None)
        if column is not None:
            stmt = stmt.where(column == value)
    sort_column = getattr(model, input.sort, None) if input.sort else None
    if sort_column is None:
        sort_column = getattr(model, "created_at", None)
    if sort_column is not None:
        stmt = stmt.order_by(sort_column.desc() if input.dir.lower() == "desc" else sort_column.asc())
    pagination = Pagination(page=input.page, page_size=input.page_size)
    return stmt.offset(pagination.skip).limit(pagination.page_size)
