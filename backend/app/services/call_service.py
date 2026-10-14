from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import CallLog
from app.schemas import CallAnalysis
from app.services.analyzer import AnalysisError, analyze_transcript


def apply_analysis(call: CallLog, result: CallAnalysis, engine: str) -> None:
    """Writes the structured analysis onto the call log's columns."""
    call.call_log_summary = result.call_log_summary
    call.interaction_notes = result.interaction_notes
    call.sentiment = result.sentiment
    call.sentiment_score = result.sentiment_score
    call.call_outcome = result.call_outcome
    call.dispute_raised = result.dispute_raised
    call.payment_commitments = [c.model_dump() for c in result.payment_commitments]
    call.risks = [r.model_dump() for r in result.risks]
    call.follow_up_actions = [a.model_dump() for a in result.follow_up_actions]
    call.analysis_status = "Completed"
    call.analysis_engine = engine
    call.analysis_error = None
    call.analyzed_at = datetime.now(timezone.utc)


def run_analysis(db: Session, call: CallLog) -> CallLog:
    """Analyzes a call transcript and writes the structured notes back to the call log."""
    if not call.transcript:
        call.analysis_status = "Failed"
        call.analysis_error = "No transcript available for this call"
        db.commit()
        return call
    try:
        result, engine = analyze_transcript(call.transcript, call.call_datetime.date(), call.customer.full_name)
    except AnalysisError as exc:
        call.analysis_status = "Failed"
        call.analysis_error = str(exc)
        db.commit()
        return call

    apply_analysis(call, result, engine)

    customer = call.customer
    call_day = call.call_datetime.date()
    if customer.last_contact_date is None or call_day > customer.last_contact_date:
        customer.last_contact_date = call_day
    db.commit()
    db.refresh(call)
    return call
