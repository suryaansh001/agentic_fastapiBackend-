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
