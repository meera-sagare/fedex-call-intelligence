from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.schemas import CallAnalysis
from app.seed import T_DISPUTE, T_HARDSHIP, T_PAID, T_PROMISE
from app.services import analyzer
from app.services.analyzer import AnalysisError, ClaudeAnalyzer, RuleBasedAnalyzer

CALL_DATE = date(2026, 10, 14)  # a Wednesday
FILL = dict(collector="Priya Sharma", contact="Michael Turner", inv1="INV-1001", inv2="INV-1002", date_str="October 21")


def analyze(template):
    return RuleBasedAnalyzer().analyze(template.format(**FILL), CALL_DATE, "Michael Turner")


def test_promise_to_pay_extracts_amount_date_and_method():
    result = analyze(T_PROMISE)
    assert result.call_outcome == "Promise to Pay"
    first = result.payment_commitments[0]
    assert first.amount == 9200.00
    assert first.due_date == "2026-10-16"  # "by Friday"
    assert first.method == "ACH"
    assert first.invoices == ["INV-1001", "INV-1002"]
    assert result.sentiment == "Positive"
    assert any(a.owner == "Collector" and a.due_date == "2026-10-17" for a in result.follow_up_actions)
    assert result.interaction_notes.startswith("- ")


def test_dispute_is_flagged_with_negative_sentiment():
    result = analyze(T_DISPUTE)
    assert result.dispute_raised
    assert result.call_outcome == "Dispute Raised"
    assert result.sentiment == "Negative"
    categories = {r.category for r in result.risks}
    assert {"Dispute", "Escalation"} <= categories
    assert any(a.owner == "Disputes Team" for a in result.follow_up_actions)


def test_hedged_promise_is_low_confidence_and_hardship_risk():
    result = analyze(T_HARDSHIP)
    assert result.payment_commitments[0].confidence == "Low"
    assert result.payment_commitments[0].amount == 5000
    assert any(r.category == "Financial Hardship" for r in result.risks)


def test_payment_already_made():
    result = analyze(T_PAID)
    assert result.call_outcome == "Payment Made"
    assert result.payment_commitments == []


def test_empty_transcript_raises():
    with pytest.raises(AnalysisError):
        RuleBasedAnalyzer().analyze("   \n", CALL_DATE, "X")


def _fake_claude(response):
    instance = ClaudeAnalyzer.__new__(ClaudeAnalyzer)
    instance.model = "claude-opus-5-5"
    instance.client = MagicMock()
    instance.client.beta.messages.parse.return_value = response
    return instance


def test_claude_analyzer_returns_parsed_output_and_sends_call_context():
    expected = analyze(T_PROMISE)
    fake = _fake_claude(SimpleNamespace(stop_reason="end_turn", parsed_output=expected))
    assert fake.analyze("Customer: hi", CALL_DATE, "Michael Turner") is expected
    kwargs = fake.client.beta.messages.parse.call_args.kwargs
    assert kwargs["output_format"] is CallAnalysis
    assert kwargs["model"] == "claude-opus-5-5"
    assert "2026-10-14" in kwargs["messages"][0]["content"]


def test_claude_refusal_raises():
    fake = _fake_claude(SimpleNamespace(stop_reason="refusal", parsed_output=None))
    with pytest.raises(AnalysisError):
        fake.analyze("Customer: hi", CALL_DATE, "X")


def test_auto_mode_falls_back_to_rules_when_claude_fails(monkeypatch):
    settings = analyzer.get_settings()
    monkeypatch.setattr(settings, "ai_engine", "auto")
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    def boom(self, *a, **k):
        raise AnalysisError("down")

    monkeypatch.setattr(ClaudeAnalyzer, "analyze", boom)
    result, engine = analyzer.analyze_transcript(T_PROMISE.format(**FILL), CALL_DATE, "Michael Turner")
    assert engine == "rules"
    assert result.call_outcome == "Promise to Pay"
