from datetime import datetime
from sqlalchemy import func, or_, select
from app.database.models import (
    Campaign,
    CampaignEvent,
    CampaignRecipient,
    Company,
    Contact,
    EmailMessage,
    LifecycleStage,
)
from app.database.session import async_session_factory


def _campaign_dict(row: Campaign) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "department": row.department,
        "owner_id": row.owner_id,
        "status": row.status,
        "type": row.type,
        "subject": row.subject,
        "body": row.body,
        "segment_filter": row.segment_filter or {},
        "scheduled_at": row.scheduled_at,
        "sent_at": row.sent_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


class CampaignService:
    async def list(self, skip: int = 0, limit: int = 100, status: str = "", q: str = ""):
        async with async_session_factory() as session:
            stmt = select(Campaign)
            if status:
                stmt = stmt.where(Campaign.status == status)
            if q:
                like = f"%{q}%"
                stmt = stmt.where(or_(Campaign.name.ilike(like), Campaign.subject.ilike(like)))
            total = int(await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
            rows = (await session.execute(stmt.order_by(Campaign.created_at.desc()).offset(skip).limit(limit))).scalars().all()
            items = []
            for row in rows:
                item = _campaign_dict(row)
                item["stats"] = await self._stats(session, row.id)
                items.append(item)
            return {"items": items, "total": total, "skip": skip, "limit": limit}

    async def _stats(self, session, campaign_id: str) -> dict:
        total = int(await session.scalar(select(func.count(CampaignRecipient.id)).where(CampaignRecipient.campaign_id == campaign_id)) or 0)
        sent = int(await session.scalar(select(func.count(CampaignRecipient.id)).where(CampaignRecipient.campaign_id == campaign_id, CampaignRecipient.sent_at.is_not(None))) or 0)
        opened = int(await session.scalar(select(func.count(CampaignRecipient.id)).where(CampaignRecipient.campaign_id == campaign_id, CampaignRecipient.opened_at.is_not(None))) or 0)
        clicked = int(await session.scalar(select(func.count(CampaignRecipient.id)).where(CampaignRecipient.campaign_id == campaign_id, CampaignRecipient.clicked_at.is_not(None))) or 0)
        replied = int(await session.scalar(select(func.count(CampaignRecipient.id)).where(CampaignRecipient.campaign_id == campaign_id, CampaignRecipient.replied_at.is_not(None))) or 0)
        converted = int(await session.scalar(select(func.count(CampaignRecipient.id)).where(CampaignRecipient.campaign_id == campaign_id, CampaignRecipient.converted_at.is_not(None))) or 0)
        return {
            "recipients": total,
            "sent": sent,
            "opened": opened,
            "clicked": clicked,
            "replied": replied,
            "converted": converted,
            "open_rate": round(opened / sent * 100, 1) if sent else 0,
            "click_rate": round(clicked / sent * 100, 1) if sent else 0,
            "reply_rate": round(replied / sent * 100, 1) if sent else 0,
            "conversion_rate": round(converted / sent * 100, 1) if sent else 0,
        }

    async def get(self, id: str):
        async with async_session_factory() as session:
            row = await session.get(Campaign, id)
            if row is None:
                return None
            data = _campaign_dict(row)
            data["stats"] = await self._stats(session, id)
            recipients = (await session.execute(select(CampaignRecipient).where(CampaignRecipient.campaign_id == id).limit(200))).scalars().all()
            data["recipients"] = [
                {
                    "id": r.id,
                    "email": r.email,
                    "status": r.status,
                    "sent_at": r.sent_at,
                    "opened_at": r.opened_at,
                    "clicked_at": r.clicked_at,
                    "replied_at": r.replied_at,
                    "converted_at": r.converted_at,
                }
                for r in recipients
            ]
            return data

    async def create(self, data: dict, owner_id: str):
        async with async_session_factory() as session:
            row = Campaign(
                name=data.get("name") or "Untitled campaign",
                department=data.get("department") or "marketing",
                owner_id=owner_id,
                status=data.get("status") or "draft",
                type=data.get("type") or "email",
                subject=data.get("subject"),
                body=data.get("body"),
                segment_filter=data.get("segment_filter") or {},
                scheduled_at=data.get("scheduled_at"),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _campaign_dict(row)

    async def update(self, id: str, data: dict):
        async with async_session_factory() as session:
            row = await session.get(Campaign, id)
            if row is None:
                return None
            for field in ("name", "department", "status", "type", "subject", "body", "segment_filter", "scheduled_at"):
                if field in data:
                    setattr(row, field, data[field])
            await session.commit()
            await session.refresh(row)
            return _campaign_dict(row)

    async def remove(self, id: str):
        async with async_session_factory() as session:
            row = await session.get(Campaign, id)
            if row:
                for model in (CampaignEvent, CampaignRecipient, EmailMessage):
                    rows = (await session.execute(select(model).where(model.campaign_id == id))).scalars().all()
                    for item in rows:
                        await session.delete(item)
                    await session.flush()
                await session.delete(row)
                await session.commit()
            return {"deleted": True}

    async def add_recipients(self, id: str, data: dict):
        async with async_session_factory() as session:
            campaign = await session.get(Campaign, id)
            if campaign is None:
                return None
            contact_ids = data.get("contact_ids") or []
            if contact_ids:
                contacts = (await session.execute(select(Contact).where(Contact.id.in_(contact_ids)))).scalars().all()
            else:
                stmt = select(Contact).where(Contact.email.is_not(None))
                segment = data.get("segment_filter") or campaign.segment_filter or {}
                if segment.get("lifecycle_stage"):
                    stmt = stmt.where(Contact.lifecycle_stage == segment["lifecycle_stage"])
                if segment.get("company_id"):
                    stmt = stmt.where(Contact.company_id == segment["company_id"])
                if segment.get("limit"):
                    stmt = stmt.limit(int(segment["limit"]))
                contacts = (await session.execute(stmt)).scalars().all()
            added = 0
            for contact in contacts:
                existing = await session.scalar(
                    select(CampaignRecipient).where(
                        CampaignRecipient.campaign_id == id,
                        CampaignRecipient.contact_id == contact.id,
                    )
                )
                if existing:
                    continue
                session.add(CampaignRecipient(
                    campaign_id=id,
                    contact_id=contact.id,
                    company_id=contact.company_id,
                    email=contact.email,
                    status="queued",
                ))
                added += 1
            await session.commit()
            return {"added": added, "recipients": await self._stats(session, id)}

    async def send(self, id: str):
        async with async_session_factory() as session:
            campaign = await session.get(Campaign, id)
            if campaign is None:
                return None
            if campaign.status == "sent":
                return {"campaign": _campaign_dict(campaign), "sent": 0, "message": "Already sent"}
            recipients = (await session.execute(select(CampaignRecipient).where(CampaignRecipient.campaign_id == id, CampaignRecipient.sent_at.is_(None)))).scalars().all()
            now = datetime.utcnow()
            for recipient in recipients:
                recipient.status = "sent"
                recipient.sent_at = now
                session.add(EmailMessage(
                    campaign_id=id,
                    contact_id=recipient.contact_id,
                    company_id=recipient.company_id,
                    direction="outbound",
                    to_email=recipient.email,
                    subject=campaign.subject,
                    body=campaign.body,
                    status="sent",
                    sent_at=now,
                    created_by_id=campaign.owner_id,
                ))
                session.add(CampaignEvent(campaign_id=id, recipient_id=recipient.id, event_type="sent", meta={"mock": True}))
            campaign.status = "sent"
            campaign.sent_at = now
            await session.commit()
            await session.refresh(campaign)
            return {"campaign": _campaign_dict(campaign), "sent": len(recipients)}

    async def event(self, id: str, data: dict):
        async with async_session_factory() as session:
            campaign = await session.get(Campaign, id)
            if campaign is None:
                return None
            event_type = data.get("event_type") or "event"
            recipient_id = data.get("recipient_id")
            now = datetime.utcnow()
            recipient = await session.get(CampaignRecipient, recipient_id) if recipient_id else None
            if recipient:
                if event_type == "open":
                    recipient.opened_at = now
                elif event_type == "click":
                    recipient.clicked_at = now
                elif event_type == "reply":
                    recipient.replied_at = now
                elif event_type == "conversion":
                    recipient.converted_at = now
            session.add(CampaignEvent(campaign_id=id, recipient_id=recipient_id, event_type=event_type, meta=data.get("meta") or {}))
            await session.commit()
            return {"ok": True}


campaign_service = CampaignService()
