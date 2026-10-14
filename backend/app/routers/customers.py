import shutil
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import CallLog, Customer
from app.schemas import CallLogListItem, CallLogOut, CustomerOut
from app.services.call_service import run_analysis
from app.services.transcriber import NoSpeechDetected, TranscriptionUnavailable, transcribe

router = APIRouter(prefix="/api/customers", tags=["customers"])

ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".mp4"}


def _get_customer(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(404, "Customer not found")
    return customer


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return _get_customer(db, customer_id)


@router.get("/{customer_id}/call-logs", response_model=list[CallLogListItem])
def list_call_logs(customer_id: int, db: Session = Depends(get_db)):
    """Call logs recorded up to and including today, newest first."""
    _get_customer(db, customer_id)
    end_of_today = datetime.combine(date.today() + timedelta(days=1), time.min, tzinfo=timezone.utc)
    stmt = (select(CallLog)
            .where(CallLog.customer_id == customer_id, CallLog.call_datetime < end_of_today)
            .order_by(CallLog.call_datetime.desc()))
    return db.scalars(stmt).all()


@router.post("/{customer_id}/call-logs", response_model=CallLogOut, status_code=201)
def upload_call(
    customer_id: int,
    audio: UploadFile | None = File(None),
    transcript: str | None = Form(None),
    direction: str = Form("Outbound"),
    duration_seconds: int = Form(0),
    db: Session = Depends(get_db),
):
    """Creates a call log from a recording (transcribed with Whisper) and/or transcript text, then analyzes it."""
    customer = _get_customer(db, customer_id)
    if audio is None and not (transcript and transcript.strip()):
        raise HTTPException(422, "Provide an audio recording or a transcript")
    if direction not in ("Inbound", "Outbound"):
        raise HTTPException(422, "direction must be Inbound or Outbound")

    settings = get_settings()
    stored_name = None
    if audio is not None:
        suffix = Path(audio.filename or "").suffix.lower()
        if suffix not in ALLOWED_AUDIO:
            raise HTTPException(415, f"Unsupported audio type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_AUDIO))}")
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        dest = upload_dir / stored_name
        with dest.open("wb") as fh:
            shutil.copyfileobj(audio.file, fh)
        if dest.stat().st_size > settings.max_upload_mb * 1024 * 1024:
            dest.unlink(missing_ok=True)
            raise HTTPException(413, f"Recording exceeds {settings.max_upload_mb} MB")
        if not (transcript and transcript.strip()):
            try:
                transcript = transcribe(dest)
            except TranscriptionUnavailable as exc:
                dest.unlink(missing_ok=True)
                raise HTTPException(503, str(exc)) from exc
            except NoSpeechDetected as exc:
                dest.unlink(missing_ok=True)
                raise HTTPException(422, str(exc)) from exc

    call = CallLog(
        customer_id=customer.id,
        collector_id=customer.collector_id,
        call_datetime=datetime.now(timezone.utc),
        duration_seconds=max(duration_seconds, 0),
        direction=direction,
        transcript=transcript.strip(),
        audio_filename=audio.filename if audio is not None else None,
        analysis_status="Pending",
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return run_analysis(db, call)
