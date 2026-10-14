from datetime import datetime, timedelta, timezone

from app.models import CallLog, Customer


def first_collector_customer(client):
    collector = client.get("/api/collectors").json()[0]
    customers = client.get(f"/api/collectors/{collector['id']}/customers").json()
    return collector, customers


def test_collectors_and_their_customers(client):
    collectors = client.get("/api/collectors").json()
    assert len(collectors) == 3
    _, customers = first_collector_customer(client)
    assert len(customers) == 4
    overdue = [float(c["overdue_amount"]) for c in customers]
    assert overdue == sorted(overdue, reverse=True)


def test_customer_search_and_missing_collector(client):
    collector, customers = first_collector_customer(client)
    name = customers[0]["full_name"].split()[0]
    hits = client.get(f"/api/collectors/{collector['id']}/customers", params={"search": name.lower()}).json()
    assert any(c["full_name"].startswith(name) for c in hits)
    assert client.get("/api/collectors/9999/customers").status_code == 404


def test_customer_detail_has_all_contact_fields(client):
    _, customers = first_collector_customer(client)
    detail = client.get(f"/api/customers/{customers[0]['id']}").json()
    for field in ("full_name", "phone_number", "alternate_phone_number", "email", "address",
                  "shipping_address", "home_address", "office_address", "status"):
        assert field in detail
    assert client.get("/api/customers/9999").status_code == 404


def test_call_logs_only_up_to_today(client, db):
    customer = db.query(Customer).first()
    db.add(CallLog(customer_id=customer.id, collector_id=customer.collector_id,
                   call_datetime=datetime.now(timezone.utc) + timedelta(days=3),
                   transcript="Customer: scheduled", analysis_status="Pending"))
    db.commit()
    logs = client.get(f"/api/customers/{customer.id}/call-logs").json()
    today = datetime.now(timezone.utc).date().isoformat()
    assert logs and all(log["call_datetime"][:10] <= today for log in logs)
    times = [log["call_datetime"] for log in logs]
    assert times == sorted(times, reverse=True)


def test_opening_pending_call_analyzes_and_persists(client, db):
    pending = db.query(CallLog).filter_by(analysis_status="Pending").first()
    body = client.get(f"/api/call-logs/{pending.id}").json()
    assert body["analysis_status"] == "Completed"
    assert body["call_log_summary"] and body["interaction_notes"]
    assert body["analysis_engine"] == "rules"
    db.expire_all()
    stored = db.get(CallLog, pending.id)
    assert stored.call_log_summary == body["call_log_summary"]
    assert stored.interaction_notes == body["interaction_notes"]


def test_reanalyze(client, db):
    call = db.query(CallLog).first()
    assert client.post(f"/api/call-logs/{call.id}/analyze").json()["analysis_status"] == "Completed"
    assert client.get("/api/call-logs/9999").status_code == 404


def test_upload_transcript_creates_analyzed_call(client):
    _, customers = first_collector_customer(client)
    cid = customers[0]["id"]
    transcript = ("Collector: Calling about invoice #INV-7777 for $1,250.00.\n"
                  "Customer: We will pay $1,250.00 on Friday by wire. Thanks!")
    resp = client.post(f"/api/customers/{cid}/call-logs",
                       data={"transcript": transcript, "direction": "Inbound", "duration_seconds": "95"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["call_outcome"] == "Promise to Pay"
    assert body["payment_commitments"][0]["amount"] == 1250.0
    ids = [c["id"] for c in client.get(f"/api/customers/{cid}/call-logs").json()]
    assert body["id"] in ids


def test_upload_validation(client):
    _, customers = first_collector_customer(client)
    cid = customers[0]["id"]
    assert client.post(f"/api/customers/{cid}/call-logs", data={}).status_code == 422
    bad = client.post(f"/api/customers/{cid}/call-logs",
                      files={"audio": ("notes.txt", b"hello", "text/plain")})
    assert bad.status_code == 415


def test_upload_audio_with_transcript_skips_transcription(client):
    _, customers = first_collector_customer(client)
    cid = customers[0]["id"]
    resp = client.post(f"/api/customers/{cid}/call-logs",
                       files={"audio": ("call.wav", b"RIFF0000WAVE", "audio/wav")},
                       data={"transcript": "Customer: We already paid that by wire."})
    assert resp.status_code == 201
    assert resp.json()["audio_filename"] == "call.wav"
    assert resp.json()["call_outcome"] == "Payment Made"


def test_portfolio_insights(client):
    collector, _ = first_collector_customer(client)
    mine = client.get("/api/insights/portfolio", params={"collector_id": collector["id"]}).json()
    everyone = client.get("/api/insights/portfolio").json()
    assert mine["customer_count"] == 4
    assert everyone["customer_count"] == 12
    assert everyone["calls_analyzed"] > 0
    assert sum(everyone["sentiment_breakdown"].values()) == everyone["calls_analyzed"]


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "ai_engine": "rules"}


def test_audio_without_transcript_is_transcribed(client, monkeypatch):
    from app.routers import customers as customers_router

    monkeypatch.setattr(customers_router, "transcribe",
                        lambda path: "Customer: We will pay $500.00 tomorrow by card. Thank you.")
    _, customers = first_collector_customer(client)
    resp = client.post(f"/api/customers/{customers[0]['id']}/call-logs",
                       files={"audio": ("call.mp3", b"ID3fake", "audio/mpeg")})
    assert resp.status_code == 201
    assert resp.json()["transcript"].startswith("Customer: We will pay")
    assert resp.json()["payment_commitments"][0]["amount"] == 500.0


def test_audio_with_no_speech_is_rejected(client, monkeypatch):
    from app.routers import customers as customers_router
    from app.services.transcriber import NoSpeechDetected

    def silent(path):
        raise NoSpeechDetected("No speech was detected in the recording")

    monkeypatch.setattr(customers_router, "transcribe", silent)
    _, customers = first_collector_customer(client)
    resp = client.post(f"/api/customers/{customers[0]['id']}/call-logs",
                       files={"audio": ("call.wav", b"RIFF", "audio/wav")})
    assert resp.status_code == 422
