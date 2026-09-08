from typing import Optional
from datetime import datetime

class EnrichmentLogService:
    async def log(self, company_id: str, source: str, status: str, error: Optional[str] = None):
        pass
