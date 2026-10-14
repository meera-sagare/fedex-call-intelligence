from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CollectorOut(ORMModel):
    id: int
    full_name: str
    email: str
    region: str


class CustomerSummaryOut(ORMModel):
    id: int
    account_number: str
    full_name: str
    company_name: str | None
    phone_number: str
    status: str
    ar_balance: Decimal
    overdue_amount: Decimal
    days_past_due: int
    risk_level: str
    last_contact_date: date | None


class CustomerOut(CustomerSummaryOut):
    collector_id: int
    alternate_phone_number: str | None
    email: str
    address: str
    shipping_address: str | None
    home_address: str | None
    office_address: str | None


# ---- AI analysis contract (shared by the Claude and rule-based analyzers) ----

class PaymentCommitment(BaseModel):
    amount: float | None = Field(description="Committed amount in account currency, null if not stated")
    due_date: str | None = Field(description="Promised payment date as YYYY-MM-DD, null if not stated")
    method: str | None = Field(description="Payment method mentioned, e.g. ACH, wire, card, cheque")
    invoices: list[str] = Field(description="Invoice numbers the commitment covers")
    confidence: Literal["High", "Medium", "Low"]


class Risk(BaseModel):
    category: Literal["Dispute", "Financial Hardship", "Broken Promise", "Escalation", "Churn", "Credit", "Other"]
    description: str
    severity: Literal["High", "Medium", "Low"]


class FollowUpAction(BaseModel):
    action: str
    owner: Literal["Collector", "Customer", "Billing", "Disputes Team", "Sales", "Other"]
    due_date: str | None = Field(description="YYYY-MM-DD, null if not stated")


class CallAnalysis(BaseModel):
    call_log_summary: str = Field(description="3-5 sentence narrative summary of the call")
    interaction_notes: str = Field(description="Concise, Oracle-ready collector notes as bullet lines starting with '- '")
    sentiment: Literal["Positive", "Neutral", "Negative"]
    sentiment_score: float = Field(description="-1.0 (very negative) to 1.0 (very positive)")
    call_outcome: Literal[
        "Promise to Pay", "Payment Made", "Dispute Raised", "Callback Requested",
        "Refused to Pay", "No Resolution", "Information Provided",
    ]
    dispute_raised: bool
    payment_commitments: list[PaymentCommitment]
    risks: list[Risk]
    follow_up_actions: list[FollowUpAction]


class CallLogListItem(ORMModel):
    id: int
    call_datetime: datetime
    duration_seconds: int
    direction: str
    sentiment: str | None
    call_outcome: str | None
    analysis_status: str
    audio_filename: str | None


class CallLogOut(CallLogListItem):
    customer_id: int
    collector_id: int
    transcript: str | None
    call_log_summary: str | None
    interaction_notes: str | None
    sentiment_score: float | None
    payment_commitments: list | None
    risks: list | None
    follow_up_actions: list | None
    dispute_raised: bool
    analysis_engine: str | None
    analysis_error: str | None
    analyzed_at: datetime | None


class PortfolioInsights(BaseModel):
    customer_count: int
    total_ar_balance: Decimal
    total_overdue: Decimal
    high_risk_customers: int
    customers_in_dispute: int
    calls_analyzed: int
    calls_pending_analysis: int
    open_commitment_amount: float
    open_commitment_count: int
    sentiment_breakdown: dict[str, int]
    outcome_breakdown: dict[str, int]
    top_risks: list[dict]
    upcoming_commitments: list[dict]
