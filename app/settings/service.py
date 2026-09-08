class SettingsService:
    async def list(self, skip: int = 0, limit: int = 25):
        return []

    async def get_by_id(self, id: str):
        return None

    async def create(self, data: dict):
        return {}

    async def update(self, id: str, data: dict):
        return {}

    async def remove(self, id: str):
        pass

Settings_service = SettingsService()
