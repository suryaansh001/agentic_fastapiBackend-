from typing import Optional

class CompanyDirectoryService:
    async def suggest(self, query: str) -> list:
        return []

    async def find_by_domain(self, domain: str) -> Optional[dict]:
        return None

company_directory = CompanyDirectoryService()
