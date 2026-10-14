from collections import Counter
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CallLog, Customer
from app.schemas import PortfolioInsights

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/portfolio", response_model=PortfolioInsights)
def portfolio_insights(collector_id: int | None = None, db: Session = Depends(get_db)):
    """Portfolio view for one collector, or the management view across all collectors when omitted."""
    cust_stmt = select(Customer)
    call_stmt = select(CallLog).join(Customer)
    if collector_id is not None:
        cust_stmt = cust_stmt.where(Customer.collector_id == collector_id)
        call_stmt = call_stmt.where(Customer.collector_id == collector_id)
    customers = db.scalars(cust_stmt).all()
    calls = db.scalars(call_stmt).all()
    names = {c.id: c.full_name for c in customers}

    analyzed = [c for c in calls if c.analysis_status == "Completed"]
    today = date.today().isoformat()
    upcoming, risk_rows = [], []
    open_amount = 0.0
    for call in analyzed:
        for pc in call.payment_commitments or []:
            if pc.get("due_date") and pc["due_date"] >= today:
                open_amount += pc.get("amount") or 0
                upcoming.append({"customer_id": call.customer_id, "customer_name": names.get(call.customer_id),
                                 "call_id": call.id, **pc})
        for risk in call.risks or []:
            risk_rows.append({"customer_id": call.customer_id, "customer_name": names.get(call.customer_id),
                              "call_id": call.id, **risk})
    severity_rank = {"High": 0, "Medium": 1, "Low": 2}
    risk_rows.sort(key=lambda r: severity_rank.get(r.get("severity"), 3))
    upcoming.sort(key=lambda p: p["due_date"])

    return PortfolioInsights(
        customer_count=len(customers),
        total_ar_balance=sum((c.ar_balance for c in customers), Decimal(0)),
        total_overdue=sum((c.overdue_amount for c in customers), Decimal(0)),
        high_risk_customers=sum(c.risk_level == "High" for c in customers),
        customers_in_dispute=sum(c.status == "In Dispute" for c in customers),
        calls_analyzed=len(analyzed),
        calls_pending_analysis=sum(c.analysis_status == "Pending" for c in calls),
        open_commitment_amount=round(open_amount, 2),
        open_commitment_count=len(upcoming),
        sentiment_breakdown=dict(Counter(c.sentiment for c in analyzed if c.sentiment)),
        outcome_breakdown=dict(Counter(c.call_outcome for c in analyzed if c.call_outcome)),
        top_risks=risk_rows[:8],
        upcoming_commitments=upcoming[:8],
    )
