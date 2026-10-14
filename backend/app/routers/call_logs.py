from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CallLog
from app.schemas import CallLogOut
from app.services.call_service import run_analysis

router = APIRouter(prefix="/api/call-logs", tags=["call-logs"])


def _get_call(db: Session, call_id: int) -> CallLog:
    call = db.get(CallLog, call_id)
    if call is None:
        raise HTTPException(404, "Call log not found")
    return call


@router.get("/{call_id}", response_model=CallLogOut)
def get_call_log(call_id: int, db: Session = Depends(get_db)):
    """Returns the call log; analyzes it first if that hasn't happened yet."""
    call = _get_call(db, call_id)
    if call.analysis_status == "Pending":
        call = run_analysis(db, call)
    return call


@router.post("/{call_id}/analyze", response_model=CallLogOut)
def reanalyze_call_log(call_id: int, db: Session = Depends(get_db)):
    return run_analysis(db, _get_call(db, call_id))
