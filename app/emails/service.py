import asyncio
import smtplib
from datetime import datetime
from email.message import EmailMessage as SMTPMessage
from sqlalchemy import or_, select
from app.agent.llm import get_llm_service
from app.config.settings import settings
from app.database.models import (
    Contact,
    Company,
    Deal,
    EmailMessage,
    EmailTemplate,
    EmailThread,
)
from app.database.session import async_session_factory


def _message_dict(row: EmailMessage) -> dict:
    return {
        "id": row.id,
        "thread_id": row.thread_id,
        "campaign_id": row.campaign_id,
        "contact_id": row.contact_id,
        "company_id": row.company_id,
        "deal_id": row.deal_id,
        "direction": row.direction,
        "from_email": row.from_email,
        "to_email": row.to_email,
        "subject": row.subject,
        "body": row.body,
        "status": row.status,
        "sent_at": row.sent_at,
        "opened_at": row.opened_at,
        "clicked_at": row.clicked_at,
        "created_at": row.created_at,
    }


class EmailService:
    async def list_messages(self, skip: int = 0, limit: int = 100, thread_id: str = "", contact_id: str = ""):
        async with async_session_factory() as session:
            stmt = select(EmailMessage)
            if thread_id:
                stmt = stmt.where(EmailMessage.thread_id == thread_id)
            if contact_id:
                stmt = stmt.where(EmailMessage.contact_id == contact_id)
            rows = (await session.execute(stmt.order_by(EmailMessage.created_at.desc()).offset(skip).limit(limit))).scalars().all()
            return {"items": [_message_dict(row) for row in rows]}

    async def list_threads(self, skip: int = 0, limit: int = 100):
        async with async_session_factory() as session:
            rows = (await session.execute(select(EmailThread).order_by(EmailThread.last_message_at.desc()).offset(skip).limit(limit))).scalars().all()
            return {
                "items": [
                    {
                        "id": row.id,
                        "subject": row.subject,
                        "company_id": row.company_id,
                        "contact_id": row.contact_id,
                        "last_message_at": row.last_message_at,
                        "message_count": row.message_count,
                    }
                    for row in rows
                ]
            }

    async def list_templates(self):
        async with async_session_factory() as session:
            rows = (await session.execute(select(EmailTemplate).order_by(EmailTemplate.name))).scalars().all()
            return {"items": [{"id": r.id, "name": r.name, "subject": r.subject, "body": r.body, "department": r.department} for r in rows]}

    async def create_template(self, data: dict, user_id: str):
        async with async_session_factory() as session:
            row = EmailTemplate(
                name=data.get("name") or "Untitled template",
                department=data.get("department"),
                subject=data.get("subject") or "",
                body=data.get("body") or "",
                created_by_id=user_id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return {"id": row.id, "name": row.name, "subject": row.subject, "body": row.body}

    async def _context(self, session, thread_id: str = "", contact_id: str = "", message_id: str = "") -> str:
        lines = []
        if message_id:
            message = await session.get(EmailMessage, message_id)
            if message:
                lines.append(f"Message subject: {message.subject or ''}")
                lines.append(f"Message body: {message.body or ''}")
                thread_id = thread_id or message.thread_id or ""
                contact_id = contact_id or message.contact_id or ""
        if thread_id:
            thread = await session.get(EmailThread, thread_id)
            if thread:
                lines.append(f"Thread subject: {thread.subject or ''}")
                messages = (await session.execute(
                    select(EmailMessage).where(EmailMessage.thread_id == thread_id).order_by(EmailMessage.created_at.desc()).limit(6)
                )).scalars().all()
                for message in reversed(messages):
                    lines.append(f"[{message.direction}] {message.subject or ''}: {(message.body or '')[:1200]}")
        if contact_id:
            contact = await session.get(Contact, contact_id)
            if contact:
                lines.append(f"Contact: {contact.first_name} {contact.last_name}, {contact.title or ''} at company {contact.company_id or ''}")
                if contact.company_id:
                    company = await session.get(Company, contact.company_id)
                    if company:
                        lines.append(f"Company: {company.name}, industry {company.industry or ''}, description {company.description or ''}")
        return "\n".join(lines) or "No CRM context available."

    async def generate_reply(self, data: dict) -> dict:
        async with async_session_factory() as session:
            context = await self._context(
                session,
                thread_id=data.get("thread_id") or "",
                contact_id=data.get("contact_id") or "",
                message_id=data.get("message_id") or "",
            )
        tone = data.get("tone") or "professional and concise"
        instructions = data.get("instructions") or "Write a helpful reply that moves the conversation forward."
        prompt = f"""You are a CRM email assistant. Write an email reply using the context below.
Tone: {tone}
Goal: {instructions}

Context:
{context}

Return only the email body. Do not include markdown fences or a subject line."""
        llm = get_llm_service()
        response = await llm.chat(
            [
                {"role": "system", "content": "You write clear, human-sounding B2B sales and support emails. Never invent facts that are not in the context."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=700,
            temperature=0.4,
        )
        body = (response.content or "").strip()
        if not body:
            body = "Hi,\n\nThanks for reaching out. I have reviewed the details and will follow up with the next steps shortly.\n\nBest,"
        subject = data.get("subject") or "Re: " + (data.get("thread_subject") or "our conversation")
        return {"subject": subject, "body": body, "provider": response.provider, "error": response.error}

    async def create_draft(self, data: dict, user_id: str) -> dict:
        async with async_session_factory() as session:
            row = EmailMessage(
                thread_id=data.get("thread_id"),
                contact_id=data.get("contact_id"),
                company_id=data.get("company_id"),
                deal_id=data.get("deal_id"),
                direction="outbound",
                from_email=data.get("from_email") or settings.SMTP_FROM,
                to_email=data.get("to_email"),
                subject=data.get("subject"),
                body=data.get("body"),
                status="draft",
                created_by_id=user_id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _message_dict(row)

    async def update_draft(self, id: str, data: dict):
        async with async_session_factory() as session:
            row = await session.get(EmailMessage, id)
            if row is None:
                return None
            for field in ("to_email", "subject", "body", "status"):
                if field in data:
                    setattr(row, field, data[field])
            await session.commit()
            await session.refresh(row)
            return _message_dict(row)

    async def send(self, data: dict, user_id: str) -> dict:
        message_id = data.get("id")
        async with async_session_factory() as session:
            row = await session.get(EmailMessage, message_id) if message_id else None
            if row is None:
                row = EmailMessage(
                    thread_id=data.get("thread_id"),
                    contact_id=data.get("contact_id"),
                    company_id=data.get("company_id"),
                    deal_id=data.get("deal_id"),
                    direction="outbound",
                    from_email=data.get("from_email") or settings.SMTP_FROM,
                    to_email=data.get("to_email"),
                    subject=data.get("subject"),
                    body=data.get("body"),
                    status="draft",
                    created_by_id=user_id,
                )
                session.add(row)
                await session.flush()
            if not row.to_email:
                return {"sent": False, "error": "Missing recipient email", "message": _message_dict(row)}
            sent = False
            error = None
            if settings.SMTP_HOST:
                try:
                    smtp_message = SMTPMessage()
                    smtp_message["From"] = row.from_email or settings.SMTP_FROM or settings.SMTP_USER
                    smtp_message["To"] = row.to_email
                    smtp_message["Subject"] = row.subject or ""
                    smtp_message.set_content(row.body or "")
                    await asyncio.to_thread(self._smtp_send, smtp_message)
                    sent = True
                except Exception as exc:
                    error = str(exc)
            else:
                sent = True
            if sent:
                row.status = "sent"
                row.sent_at = datetime.utcnow()
            else:
                row.status = "failed"
            await session.commit()
            await session.refresh(row)
            return {"sent": sent, "mock": not bool(settings.SMTP_HOST), "error": error, "message": _message_dict(row)}

    def _smtp_send(self, message: SMTPMessage):
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
            server.send_message(message)


email_service = EmailService()
