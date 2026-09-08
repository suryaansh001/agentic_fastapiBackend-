from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Integer, Float, Json, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
import enum

class DealStage(str, enum.Enum):
    DEMO_BOOKED = "DEMO_BOOKED"
    QUALIFIED_TO_BUY = "QUALIFIED_TO_BUY"
    UNQUALIFIED_TO_BUY = "UNQUALIFIED_TO_BUY"
    DECISION_MAKER_BOUGHT_IN = "DECISION_MAKER_BOUGHT_IN"
    CONTRACT_SENT = "CONTRACT_SENT"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"

class LifecycleStage(str, enum.Enum):
    SUBSCRIBER = "SUBSCRIBER"
    LEAD = "LEAD"
    MARKETING_QUALIFIED_LEAD = "MARKETING_QUALIFIED_LEAD"
    SALES_QUALIFIED_LEAD = "SALES_QUALIFIED_LEAD"
    OPPORTUNITY = "OPPORTUNITY"
    CUSTOMER = "CUSTOMER"
    EVANGELIST = "EVANGELIST"
    OTHER = "OTHER"

class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    OPEN_DEAL = "OPEN_DEAL"
    UNQUALIFIED = "UNQUALIFIED"
    ATTEMPTED_TO_CONTACT = "ATTEMPTED_TO_CONTACT"
    CONNECTED = "CONNECTED"
    BAD_TIMING = "BAD_TIMING"

class ForecastCategory(str, enum.Enum):
    PIPELINE = "PIPELINE"
    BEST_CASE = "BEST_CASE"
    COMMIT = "COMMIT"
    CLOSED = "CLOSED"
    OMITTED = "OMITTED"

class RecordSource(str, enum.Enum):
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    ENRICHMENT = "ENRICHMENT"
    API = "API"

class ActivityType(str, enum.Enum):
    NOTE = "NOTE"
    CALL = "CALL"
    EMAIL = "EMAIL"
    MEETING = "MEETING"
    TASK = "TASK"
    STAGE_CHANGE = "STAGE_CHANGE"
    LIFECYCLE_CHANGE = "LIFECYCLE_CHANGE"
    ENRICHMENT = "ENRICHMENT"

class EnrichmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    image: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owned_companies: Mapped[List["Company"]] = relationship("Company", back_populates="owner", foreign_keys="[Company.owner_id]")
    owned_contacts: Mapped[List["Contact"]] = relationship("Contact", back_populates="owner", foreign_keys="[Contact.owner_id]")
    owned_deals: Mapped[List["Deal"]] = relationship("Deal", back_populates="owner", foreign_keys="[Deal.owner_id]")

    members: Mapped[List["Member"]] = relationship("Member", back_populates="user")
    invitations: Mapped[List["Invitation"]] = relationship("Invitation", back_populates="inviter")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

class Company(Base):
    __tablename__ = "company"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    domain: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    website: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    logo_dark_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    icon_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    icon_dark_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    icon_tone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    brand_color: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sub_industry: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    twitter_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pricing_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    careers_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("user.id"), nullable=True, index=True)
    primary_contact_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    lifecycle_stage: Mapped[LifecycleStage] = mapped_column(SAEnum(LifecycleStage), default=LifecycleStage.LEAD)
    lifecycle_stage_changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    lead_status: Mapped[Optional[LeadStatus]] = mapped_column(SAEnum(LeadStatus), nullable=True)
    record_source: Mapped[RecordSource] = mapped_column(SAEnum(RecordSource), default=RecordSource.MANUAL)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    enrichment_status: Mapped[EnrichmentStatus] = mapped_column(SAEnum(EnrichmentStatus), default=EnrichmentStatus.PENDING)
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    enrichment_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    custom_fields: Mapped[dict] = mapped_column(Json, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped[Optional["User"]] = relationship("User", back_populates="owned_companies", foreign_keys=[owner_id])
    primary_contact: Mapped[Optional["Contact"]] = relationship("Contact", foreign_keys=[primary_contact_id])
    contacts: Mapped[List["Contact"]] = relationship("Contact", back_populates="company", foreign_keys="[Contact.company_id]")
    deals: Mapped[List["Deal"]] = relationship("Deal", back_populates="company", foreign_keys="[Deal.company_id]")
    activities: Mapped[List["Activity"]] = relationship("Activity", back_populates="company")
    email_threads: Mapped[List["EmailThread"]] = relationship("EmailThread", back_populates="company")
    calendar_events: Mapped[List["CalendarEvent"]] = relationship("CalendarEvent", back_populates="company")
    field_values: Mapped[List["FieldValue"]] = relationship("FieldValue", back_populates="company")
    attachments: Mapped[List["Attachment"]] = relationship("Attachment", back_populates="company")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

class Contact(Base):
    __tablename__ = "contact"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    seniority: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    function: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    twitter_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    socials_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    company_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("company.id"), nullable=True, index=True)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("user.id"), nullable=True, index=True)
    lifecycle_stage: Mapped[LifecycleStage] = mapped_column(SAEnum(LifecycleStage), default=LifecycleStage.LEAD)
    lifecycle_stage_changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    lead_status: Mapped[Optional[LeadStatus]] = mapped_column(SAEnum(LeadStatus), nullable=True)
    buying_role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    record_source: Mapped[RecordSource] = mapped_column(SAEnum(RecordSource), default=RecordSource.MANUAL)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    enrichment_status: Mapped[EnrichmentStatus] = mapped_column(SAEnum(EnrichmentStatus), default=EnrichmentStatus.PENDING)
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    enrichment_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    custom_fields: Mapped[dict] = mapped_column(Json, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="contacts", foreign_keys=[company_id])
    owner: Mapped[Optional["User"]] = relationship("User", back_populates="owned_contacts", foreign_keys=[owner_id])
    deals: Mapped[List["DealContact"]] = relationship("DealContact", back_populates="contact")
    activities: Mapped[List["Activity"]] = relationship("Activity", back_populates="contact")
    email_threads: Mapped[List["EmailThread"]] = relationship("EmailThread", back_populates="contact")
    calendar_events: Mapped[List["CalendarEvent"]] = relationship("CalendarEvent", back_populates="contact")
    field_values: Mapped[List["FieldValue"]] = relationship("FieldValue", back_populates="contact")

class Deal(Base):
    __tablename__ = "deal"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    company_id: Mapped[str] = mapped_column(String, ForeignKey("company.id"), nullable=False)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False, index=True)
    stage: Mapped[DealStage] = mapped_column(SAEnum(DealStage), default=DealStage.DEMO_BOOKED)
    stage_changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    forecast_category: Mapped[ForecastCategory] = mapped_column(SAEnum(ForecastCategory), default=ForecastCategory.PIPELINE)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="USD")
    expected_close_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    record_source: Mapped[RecordSource] = mapped_column(SAEnum(RecordSource), default=RecordSource.MANUAL)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    base_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    base_currency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fx_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fx_rate_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    custom_fields: Mapped[dict] = mapped_column(Json, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    company: Mapped["Company"] = relationship("Company", back_populates="deals")
    owner: Mapped["User"] = relationship("User", back_populates="owned_deals", foreign_keys=[owner_id])
    contacts: Mapped[List["DealContact"]] = relationship("DealContact", back_populates="deal")
    activities: Mapped[List["Activity"]] = relationship("Activity", back_populates="deal")
    field_values: Mapped[List["FieldValue"]] = relationship("FieldValue", back_populates="deal")

class Activity(Base):
    __tablename__ = "activity"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[ActivityType] = mapped_column(SAEnum(ActivityType))
    subject: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    company_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("company.id"), nullable=True, index=True)
    contact_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("contact.id"), nullable=True, index=True)
    deal_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("deal.id"), nullable=True, index=True)
    created_by_id: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(Json, nullable=True)
    email_thread_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    calendar_event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="activities")
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="activities")
    deal: Mapped[Optional["Deal"]] = relationship("Deal", back_populates="activities")
    created_by: Mapped["User"] = relationship("User")

class FieldDefinition(Base):
    __tablename__ = "field_definition"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entity: Mapped[str] = mapped_column(String, nullable=False, index=True)
    key: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    agent_filled: Mapped[bool] = mapped_column(Boolean, default=True)
    agent_brief: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    show_on_sheet: Mapped[bool] = mapped_column(Boolean, default=True)
    show_on_table: Mapped[bool] = mapped_column(Boolean, default=False)
    show_on_filter: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

class FieldValue(Base):
    __tablename__ = "field_value"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    field_id: Mapped[str] = mapped_column(String, ForeignKey("field_definition.id"), nullable=False, index=True)
    company_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("company.id"), nullable=True, index=True)
    contact_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("contact.id"), nullable=True, index=True)
    deal_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("deal.id"), nullable=True, index=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    number: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    bool: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    option_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("field_option.id"), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("user.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class SavedView(Base):
    __tablename__ = "saved_view"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entity: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    filters: Mapped[dict] = mapped_column(Json, nullable=False, default="{}")
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class CompanyContact(Base):
    __tablename__ = "company_contact"
    company_id: Mapped[str] = mapped_column(String, ForeignKey("company.id"), primary_key=True)
    contact_id: Mapped[str] = mapped_column(String, ForeignKey("contact.id"), primary_key=True)
    is_primary_company: Mapped[bool] = mapped_column(Boolean, default=False)
    is_primary_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class CompanyDeal(Base):
    __tablename__ = "company_deal"
    company_id: Mapped[str] = mapped_column(String, ForeignKey("company.id"), primary_key=True)
    deal_id: Mapped[str] = mapped_column(String, ForeignKey("deal.id"), primary_key=True)
    is_primary_company: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class DealContact(Base):
    __tablename__ = "deal_contact"
    deal_id: Mapped[str] = mapped_column(String, ForeignKey("deal.id"), primary_key=True)
    contact_id: Mapped[str] = mapped_column(String, ForeignKey("contact.id"), primary_key=True)
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_primary_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class AppSetting(Base):
    __tablename__ = "app_setting"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_model_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    agent_model_context_window: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    context_dev_api_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reporting_currency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rates_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    archive_retention_days: Mapped[int] = mapped_column(Integer, default=180)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class Attachment(Base):
    __tablename__ = "attachment"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    pathname: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("company.id"), nullable=True, index=True)
    contact_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("contact.id"), nullable=True, index=True)
    deal_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("deal.id"), nullable=True, index=True)
    activity_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("activity.id"), nullable=True, index=True)
    uploaded_by_id: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class EmailThread(Base):
    __tablename__ = "email_thread"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    root_message_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    company_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("company.id"), nullable=True, index=True)
    contact_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("contact.id"), nullable=True, index=True)
    first_message_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class CalendarEvent(Base):
    __tablename__ = "calendar_event"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    ical_uid: Mapped[str] = mapped_column(String, nullable=False)
    original_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recurring_event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    conference_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    organizer_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    company_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("company.id"), nullable=True, index=True)
    contact_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("contact.id"), nullable=True, index=True)
    google_event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    synced_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class ExchangeRate(Base):
    __tablename__ = "exchange_rate"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    base_currency: Mapped[str] = mapped_column(String, nullable=False, index=True)
    quote_currency: Mapped[str] = mapped_column(String, nullable=False, index=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

class WorkspaceProfile(Base):
    __tablename__ = "workspace_profile"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    website: Mapped[str] = mapped_column(String, nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[dict] = mapped_column(Json, nullable=False, default="{}")
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class SuppressedDomain(Base):
    __tablename__ = "suppressed_domain"
    domain: Mapped[str] = mapped_column(String, primary_key=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class SuppressedContact(Base):
    __tablename__ = "suppressed_contact"
    email: Mapped[str] = mapped_column(String, primary_key=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class Organization(Base):
    __tablename__ = "organization"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    logo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    metadata: Mapped[Optional[dict]] = mapped_column(Json, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class Member(Base):
    __tablename__ = "member"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organization.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class Invitation(Base):
    __tablename__ = "invitation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organization.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    inviter_id: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
