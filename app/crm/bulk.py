from typing import List, Dict

async def bulk_create_companies(rows: List[Dict]) -> Dict:
    created = []
    skipped = []
    return {"created": created, "skipped": skipped, "total": len(rows)}
