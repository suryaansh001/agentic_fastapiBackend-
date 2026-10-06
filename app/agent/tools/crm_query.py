"""Allow-listed, read-only CRM query service.

Replaces raw LLM-generated SQL execution. The LLM may only select one of the
operations below with validated parameters; every query is parameterized through
SQLAlchemy against the application models. No raw SQL string from the model is
ever executed.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Activity, Company, Contact, Deal

MAX_ROWS = 100


class CrmQueryError(Exception):
    pass


def _limit(value: Any, default: int = 25, maximum: int = MAX_ROWS) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, maximum))


def _row_to_dict(row) -> Dict[str, Any]:
    """Flatten a RowMapping into column name -> value.

    Whole-entity selects (``select(Deal)``) produce a single mapping key
    holding the ORM instance; expand it into its column values so every
    operation returns the same rows/columns shape.
    """
    out: Dict[str, Any] = {}
    for key, value in row.items():
        table = getattr(value, "__table__", None)
        if table is not None:
            for column in table.columns:
                out[column.name] = getattr(value, column.name)
        else:
            out[key] = value
    return out


async def _rows(session: AsyncSession, stmt) -> List[Dict[str, Any]]:
    result = await session.execute(stmt)
    return [_row_to_dict(row) for row in result.mappings().all()]


def _serialize(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return str(value)


class CrmQueryService:
    """Read-only CRM queries. Each operation is an allow-listed, parameterized query."""

    async def list_deals(
        self,
        session: AsyncSession,
        stage: Optional[str] = None,
        owner_id: Optional[str] = None,
        company_id: Optional[str] = None,
        limit: Any = 25,
    ) -> Dict[str, Any]:
        stmt = select(Deal).limit(_limit(limit))
        if stage:
            stmt = stmt.where(Deal.stage == stage)
        if owner_id:
            stmt = stmt.where(Deal.owner_id == owner_id)
        if company_id:
            stmt = stmt.where(Deal.company_id == company_id)
        stmt = stmt.order_by(Deal.created_at.desc())
        rows = await _rows(session, stmt)
        return {"operation": "list_deals", "count": len(rows), "rows": [[_serialize(v) for v in r.values()] for r in rows], "columns": list(rows[0].keys()) if rows else []}

    async def search_contacts(
        self,
        session: AsyncSession,
        query: str = "",
        limit: Any = 25,
    ) -> Dict[str, Any]:
        q = (query or "").strip()
        if len(q) < 2:
            raise CrmQueryError("search query must be at least 2 characters")
        cond = or_(
            Contact.first_name.ilike(f"%{q}%"),
            Contact.last_name.ilike(f"%{q}%"),
            Contact.email.ilike(f"%{q}%"),
        )
        stmt = select(Contact).where(cond).limit(_limit(limit)).order_by(Contact.created_at.desc())
        rows = await _rows(session, stmt)
        return {"operation": "search_contacts", "count": len(rows), "rows": [[_serialize(v) for v in r.values()] for r in rows], "columns": list(rows[0].keys()) if rows else []}

    async def search_companies(
        self,
        session: AsyncSession,
        query: str = "",
        limit: Any = 25,
    ) -> Dict[str, Any]:
        q = (query or "").strip()
        if len(q) < 2:
            raise CrmQueryError("search query must be at least 2 characters")
        cond = or_(Company.name.ilike(f"%{q}%"), Company.domain.ilike(f"%{q}%"))
        stmt = select(Company).where(cond).limit(_limit(limit)).order_by(Company.created_at.desc())
        rows = await _rows(session, stmt)
        return {"operation": "search_companies", "count": len(rows), "rows": [[_serialize(v) for v in r.values()] for r in rows], "columns": list(rows[0].keys()) if rows else []}

    async def deal_pipeline(
        self,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        stmt = (
            select(Deal.stage, func.count(Deal.id).label("count"), func.sum(Deal.amount).label("total_amount"))
            .group_by(Deal.stage)
            .order_by(Deal.stage)
        )
        rows = await _rows(session, stmt)
        return {"operation": "deal_pipeline", "count": len(rows), "rows": [[_serialize(v) for v in r.values()] for r in rows], "columns": ["stage", "count", "total_amount"]}

    async def contact_timeline(
        self,
        session: AsyncSession,
        contact_id: str,
        limit: Any = 25,
    ) -> Dict[str, Any]:
        if not contact_id:
            raise CrmQueryError("contact_id is required")
        stmt = (
            select(Activity)
            .where(Activity.contact_id == contact_id)
            .limit(_limit(limit))
            .order_by(Activity.created_at.desc())
        )
        rows = await _rows(session, stmt)
        return {"operation": "contact_timeline", "count": len(rows), "rows": [[_serialize(v) for v in r.values()] for r in rows], "columns": list(rows[0].keys()) if rows else []}

    async def company_contacts(
        self,
        session: AsyncSession,
        company_id: str,
        limit: Any = 25,
    ) -> Dict[str, Any]:
        if not company_id:
            raise CrmQueryError("company_id is required")
        stmt = (
            select(Contact)
            .where(Contact.company_id == company_id)
            .limit(_limit(limit))
            .order_by(Contact.created_at.desc())
        )
        rows = await _rows(session, stmt)
        return {"operation": "company_contacts", "count": len(rows), "rows": [[_serialize(v) for v in r.values()] for r in rows], "columns": list(rows[0].keys()) if rows else []}

    async def deal_summary(
        self,
        session: AsyncSession,
        deal_id: str,
    ) -> Dict[str, Any]:
        if not deal_id:
            raise CrmQueryError("deal_id is required")
        stmt = select(Deal).where(Deal.id == deal_id).limit(1)
        rows = await _rows(session, stmt)
        if not rows:
            raise CrmQueryError(f"deal {deal_id} not found")
        return {"operation": "deal_summary", "count": 1, "rows": [[_serialize(v) for v in r.values()] for r in rows], "columns": list(rows[0].keys())}

    # Operation registry: name -> (handler, required params, optional params)
    OPERATIONS = {
        "list_deals": (list_deals, [], ["stage", "owner_id", "company_id", "limit"]),
        "search_contacts": (search_contacts, [], ["query", "limit"]),
        "search_companies": (search_companies, [], ["query", "limit"]),
        "deal_pipeline": (deal_pipeline, [], []),
        "contact_timeline": (contact_timeline, ["contact_id"], ["limit"]),
        "company_contacts": (company_contacts, ["company_id"], ["limit"]),
        "deal_summary": (deal_summary, ["deal_id"], []),
    }

    async def execute(self, session: AsyncSession, operation: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entry = self.OPERATIONS.get(operation)
        if entry is None:
            raise CrmQueryError(f"Unknown CRM query operation: {operation}")
        handler, required, optional = entry
        params = params or {}
        unknown = set(params.keys()) - set(required) - set(optional)
        if unknown:
            raise CrmQueryError(f"Unknown parameters for {operation}: {sorted(unknown)}")
        missing = [p for p in required if not params.get(p)]
        if missing:
            raise CrmQueryError(f"Missing required parameters for {operation}: {missing}")
        kwargs = {k: params[k] for k in set(required) | set(optional) if k in params}
        return await handler(self, session, **kwargs)


crm_query_service = CrmQueryService()
