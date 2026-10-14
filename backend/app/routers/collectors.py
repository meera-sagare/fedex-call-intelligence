from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Collector, Customer
from app.schemas import CollectorOut, CustomerSummaryOut

router = APIRouter(prefix="/api/collectors", tags=["collectors"])


@router.get("", response_model=list[CollectorOut])
def list_collectors(db: Session = Depends(get_db)):
    return db.scalars(select(Collector).order_by(Collector.full_name)).all()


@router.get("/{collector_id}/customers", response_model=list[CustomerSummaryOut])
def list_collector_customers(
    collector_id: int,
    search: str | None = Query(None, max_length=100),
    status: str | None = None,
    db: Session = Depends(get_db),
):
    if db.get(Collector, collector_id) is None:
        raise HTTPException(404, "Collector not found")
    stmt = select(Customer).where(Customer.collector_id == collector_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Customer.full_name.ilike(like), Customer.company_name.ilike(like),
                              Customer.account_number.ilike(like)))
    if status:
        stmt = stmt.where(Customer.status == status)
    stmt = stmt.order_by(Customer.overdue_amount.desc(), Customer.full_name)
    return db.scalars(stmt).all()
