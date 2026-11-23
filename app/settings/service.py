from app.database.models import AppConfig
from app.database.session import async_session_factory

DEFAULT_SETTINGS = {
    "email_notifications": True,
    "slack_notifications": False,
    "activity_digest": True,
    "default_currency": "USD",
    "fiscal_year_start": 1,
    "anonymize_data": False,
    "gdpr_mode": False,
}


class SettingsService:
    async def get(self) -> dict:
        async with async_session_factory() as session:
            row = await session.get(AppConfig, "settings")
            return {**DEFAULT_SETTINGS, **(row.value if row else {})}

    async def update(self, data: dict) -> dict:
        async with async_session_factory() as session:
            row = await session.get(AppConfig, "settings")
            if row is None:
                row = AppConfig(key="settings", value={})
                session.add(row)
            row.value = {**(row.value or {}), **data}
            await session.commit()
            return row.value


settings_service = SettingsService()
