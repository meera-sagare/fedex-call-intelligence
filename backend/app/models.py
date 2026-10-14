from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")


class Collector(Base):
    __tablename__ = "collectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    region: Mapped[str] = mapped_column(String(80))

    customers: Mapped[list["Customer"]] = relationship(back_populates="collector")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("collectors.id"), index=True)
    account_number: Mapped[str] = mapped_column(String(30), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    company_name: Mapped[str | None] = mapped_column(String(150))
    phone_number: Mapped[str] = mapped_column(String(30))
    alternate_phone_number: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300))
    shipping_address: Mapped[str | None] = mapped_column(String(300))
    home_address: Mapped[str | None] = mapped_column(String(300))
    office_address: Mapped[str | None] = mapped_column(String(300))
    # Active | Past Due | In Dispute | Promise to Pay | Collections Hold | Closed
    status: Mapped[str] = mapped_column(String(40))
    ar_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    overdue_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    days_past_due: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(20), default="Low")  # Low | Medium | High
    last_contact_date: Mapped[date | None] = mapped_column(Date)

    collector: Mapped[Collector] = relationship(back_populates="customers")
    call_logs: Mapped[list["CallLog"]] = relationship(back_populates="customer", order_by="desc(CallLog.call_datetime)")


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("collectors.id"), index=True)
    call_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    direction: Mapped[str] = mapped_column(String(10), default="Outbound")  # Inbound | Outbound
    transcript: Mapped[str | None] = mapped_column(Text)
    audio_filename: Mapped[str | None] = mapped_column(String(255))

    # AI output — written back after analysis.
    call_log_summary: Mapped[str | None] = mapped_column(Text)
    interaction_notes: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[str | None] = mapped_column(String(20))  # Positive | Neutral | Negative
    sentiment_score: Mapped[float | None]
    payment_commitments: Mapped[list | None] = mapped_column(JsonType)
    risks: Mapped[list | None] = mapped_column(JsonType)
    follow_up_actions: Mapped[list | None] = mapped_column(JsonType)
    dispute_raised: Mapped[bool] = mapped_column(Boolean, default=False)
    call_outcome: Mapped[str | None] = mapped_column(String(60))
    analysis_status: Mapped[str] = mapped_column(String(20), default="Pending")  # Pending | Completed | Failed
    analysis_engine: Mapped[str | None] = mapped_column(String(60))
    analysis_error: Mapped[str | None] = mapped_column(Text)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped[Customer] = relationship(back_populates="call_logs")
