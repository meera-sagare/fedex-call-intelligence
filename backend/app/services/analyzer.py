"""Turns a call transcript into structured collections notes.

Two interchangeable engines share the `CallAnalysis` contract:
  * ClaudeAnalyzer  - Anthropic Claude with structured outputs (used when credentials are configured)
  * RuleBasedAnalyzer - deterministic keyword/regex analyzer so the app works offline and in tests
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta

import anthropic

from app.config import get_settings
from app.schemas import CallAnalysis, FollowUpAction, PaymentCommitment, Risk

log = logging.getLogger(__name__)


class AnalysisError(RuntimeError):
    pass


SYSTEM_PROMPT = """You are a call-intelligence assistant for the ABC Accounts Receivable collections team.
You read transcripts of calls between a ABC collector and a customer (B2B shipping accounts) and
produce structured post-call documentation that replaces the collector's manual note-taking and Oracle updates.

Domain context:
- Collectors follow up on overdue invoices, take promises to pay (PTP), log disputes (billing errors,
  duplicate charges, damaged/lost shipments, incorrect surcharges, rate disagreements), and schedule follow-ups.
- A payment commitment needs at least an amount or a date that the customer agreed to. Hedged statements
  ("I'll try", "maybe next month") are Low confidence. Do not invent amounts, dates or invoice numbers.
- Resolve relative dates ("this Friday", "end of month") against the call date given with the transcript
  and output them as YYYY-MM-DD.
- Risks: disputes, financial hardship, broken or repeated promises, escalation threats, intent to move
  volume to another carrier (churn), credit concerns.
- interaction_notes are what the collector would paste into Oracle: terse, factual, bullet lines that start
  with "- ", covering contact made, invoices discussed, customer position, commitments, and next steps.
- sentiment reflects the customer's attitude over the whole call, not the collector's."""


class ClaudeAnalyzer:
    name = "claude"

    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def analyze(self, transcript: str, call_date: date, customer_name: str) -> CallAnalysis:
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                output_config={"effort": "medium"},
                output_format=CallAnalysis,
                # Re-route automatically if a safety classifier declines the request.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{
                    "role": "user",
                    "content": (
                        f"Call date: {call_date.isoformat()}\n"
                        f"Customer: {customer_name}\n\n"
                        f"<transcript>\n{transcript}\n</transcript>"
                    ),
                }],
            )
        except anthropic.AuthenticationError as exc:
            raise AnalysisError("Anthropic credentials were rejected") from exc
        except anthropic.RateLimitError as exc:
            raise AnalysisError("Anthropic rate limit reached; retry shortly") from exc
        except anthropic.APIStatusError as exc:
            raise AnalysisError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise AnalysisError("Could not reach the Anthropic API") from exc

        if response.stop_reason == "refusal":
            raise AnalysisError("The model declined to analyze this transcript")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise AnalysisError("The model response was incomplete")
        return response.parsed_output


# --------------------------------------------------------------------------- rule-based engine

_POSITIVE = {
    "thank", "thanks", "great", "appreciate", "happy", "glad", "sure", "absolutely", "perfect",
    "helpful", "sounds good", "no problem", "of course", "definitely", "resolved",
}
_NEGATIVE = {
    "frustrated", "unacceptable", "angry", "ridiculous", "upset", "annoyed", "terrible", "worst",
    "disappointed", "complain", "not paying", "won't pay", "refuse", "lawyer", "cancel", "fed up",
    "again", "never", "incorrect", "wrong",
}
_DISPUTE = [
    "dispute", "overcharged", "overcharge", "incorrect", "wrong amount", "duplicate", "double billed",
    "double-billed", "damaged", "never received", "not delivered", "lost shipment", "surcharge", "didn't order",
    "billing error", "don't agree", "do not agree",
]
_HARDSHIP = ["cash flow", "can't afford", "cannot afford", "tight", "layoff", "bankrupt", "struggling", "short on funds", "behind on"]
_ESCALATION = ["manager", "supervisor", "escalate", "lawyer", "legal", "complaint"]
_CHURN = ["another carrier", "switch to", "ups", "dhl", "moving our business", "cancel our account", "close the account"]
_BROKEN = ["last time", "said that before", "promised last", "missed the payment", "again"]
_CALLBACK = ["call me back", "call back", "follow up", "check with", "get back to you", "talk to my"]
_PAID = ["already paid", "payment went out", "sent the payment", "paid it", "processed the payment"]
_REFUSE = ["not paying", "won't pay", "will not pay", "refuse to pay"]

_AMOUNT_RE = re.compile(r"\$\s?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)")
_INVOICE_RE = re.compile(
    r"\b(INV-[A-Z0-9-]*\d[A-Z0-9-]*)|\binvoice\s*(?:#|number|no\.?)\s*([A-Z0-9-]*\d[A-Z0-9-]*)", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_MONTH_DATE_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b", re.IGNORECASE
)
_COMMIT_RE = re.compile(
    r"\b(?:i|we)(?:'ll| will| can| could)?\s+(?:try to\s+|be able to\s+)?(?:pay|send|wire|process|do)\b"
    r"|\bschedul\w* the payment|\bagree to pay", re.IGNORECASE)
_CLAUSE_SPLIT_RE = re.compile(r",\s*and\s+|;\s*|\s+and\s+(?=the (?:rest|remaining|second|balance))", re.IGNORECASE)
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_METHODS = {"ach": "ACH", "wire": "Wire", "credit card": "Card", "card": "Card", "cheque": "Cheque", "check": "Cheque", "online": "Online portal", "portal": "Online portal"}


def _speaker_lines(transcript: str) -> list[tuple[str, str]]:
    lines = []
    for raw in transcript.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        speaker, sep, text = raw.partition(":")
        if sep and len(speaker) <= 20:
            lines.append((speaker.strip().lower(), text.strip()))
        else:
            lines.append(("unknown", raw))
    return lines


def _has_any(text: str, words) -> bool:
    return any(w in text for w in words)


def _resolve_date(text: str, call_date: date) -> date | None:
    """Resolves the first date expression in the text (absolute or relative to the call date)."""
    lowered = text.lower()
    found: list[tuple[int, date]] = []
    if m := _ISO_DATE_RE.search(text):
        try:
            found.append((m.start(), date.fromisoformat(m.group(1))))
        except ValueError:
            pass
    if m := _MONTH_DATE_RE.search(text):
        month = datetime.strptime(m.group(1)[:3].title(), "%b").month
        try:
            candidate = date(call_date.year, month, int(m.group(2)))
            if candidate < call_date - timedelta(days=7):
                candidate = candidate.replace(year=call_date.year + 1)
            found.append((m.start(), candidate))
        except ValueError:
            pass
    if (i := lowered.find("tomorrow")) >= 0:
        found.append((i, call_date + timedelta(days=1)))
    for phrase in ("end of the month", "end of month", "month end"):
        if (i := lowered.find(phrase)) >= 0:
            first_of_next = (call_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            found.append((i, first_of_next - timedelta(days=1)))
    if (i := lowered.find("next week")) >= 0:
        found.append((i, call_date + timedelta(days=7 - call_date.weekday())))
    for idx, day in enumerate(_WEEKDAYS):
        if (i := lowered.find(day)) >= 0:
            found.append((i, call_date + timedelta(days=(idx - call_date.weekday()) % 7 or 7)))
    return min(found)[1] if found else None


class RuleBasedAnalyzer:
    name = "rules"

    def analyze(self, transcript: str, call_date: date, customer_name: str) -> CallAnalysis:
        lines = _speaker_lines(transcript)
        if not lines:
            raise AnalysisError("Transcript is empty")
        customer_text = " ".join(t for s, t in lines if not s.startswith(("collector", "agent", "abc"))).lower()
        full_text = " ".join(t for _, t in lines)
        full_lower = full_text.lower()

        invoices = sorted({(a or b).upper().rstrip('-') for a, b in _INVOICE_RE.findall(full_text)})
        method = next((label for key, label in _METHODS.items() if re.search(rf"\b{key}\b", full_lower)), None)

        # Payment commitments: customer lines that agree to pay, with amount/date taken from that line or the
        # collector line it answers.
        commitments: list[PaymentCommitment] = []
        for i, (speaker, text) in enumerate(lines):
            if speaker.startswith(("collector", "agent", "abc")) or not _COMMIT_RE.search(text):
                continue
            hedged = _has_any(text.lower(), ("try", "maybe", "hopefully", "might", "should be able"))
            # "I can pay $X by Friday, and the rest by month end" holds two commitments.
            clauses = [c for c in _CLAUSE_SPLIT_RE.split(text) if c.strip()]
            for n, clause in enumerate(clauses):
                amount_match = _AMOUNT_RE.search(clause)
                due = _resolve_date(clause, call_date)
                if n == 0 and not (amount_match or due) and i:
                    # "Yes, I can do that" - terms come from the collector's proposal.
                    amount_match = _AMOUNT_RE.search(lines[i - 1][1])
                    due = _resolve_date(lines[i - 1][1], call_date)
                if not (amount_match or due):
                    continue
                commitments.append(PaymentCommitment(
                    amount=float(amount_match.group(1).replace(",", "")) if amount_match else None,
                    due_date=due.isoformat() if due else None,
                    method=method,
                    invoices=invoices,
                    confidence="Low" if hedged else ("High" if amount_match and due else "Medium"),
                ))

        dispute = _has_any(customer_text, _DISPUTE)
        risks: list[Risk] = []
        if dispute:
            risks.append(Risk(category="Dispute", severity="High",
                              description="Customer disputes charges on the account; payment likely held until resolved."))
        if _has_any(customer_text, _HARDSHIP):
            risks.append(Risk(category="Financial Hardship", severity="High",
                              description="Customer indicated cash-flow or financial difficulty."))
        if _has_any(customer_text, _ESCALATION):
            risks.append(Risk(category="Escalation", severity="Medium",
                              description="Customer requested escalation or referenced management/legal action."))
        if _has_any(customer_text, _CHURN):
            risks.append(Risk(category="Churn", severity="Medium",
                              description="Customer mentioned moving volume to another carrier or closing the account."))
        if _has_any(full_lower, _BROKEN) and commitments:
            risks.append(Risk(category="Broken Promise", severity="Medium",
                              description="A previous commitment appears to have been missed; monitor the new promise."))

        # Sentiment from customer speech.
        pos = sum(customer_text.count(w) for w in _POSITIVE)
        neg = sum(customer_text.count(w) for w in _NEGATIVE)
        score = 0.0 if pos + neg == 0 else round((pos - neg) / (pos + neg), 2)
        sentiment = "Positive" if score > 0.2 else "Negative" if score < -0.2 else "Neutral"

        if _has_any(customer_text, _PAID):
            outcome = "Payment Made"
        elif commitments:
            outcome = "Promise to Pay"
        elif dispute:
            outcome = "Dispute Raised"
        elif _has_any(customer_text, _REFUSE):
            outcome = "Refused to Pay"
        elif _has_any(full_lower, _CALLBACK):
            outcome = "Callback Requested"
        else:
            outcome = "Information Provided" if sentiment != "Negative" else "No Resolution"

        actions: list[FollowUpAction] = []
        for c in commitments:
            check = date.fromisoformat(c.due_date) + timedelta(days=1) if c.due_date else call_date + timedelta(days=3)
            actions.append(FollowUpAction(action=f"Verify receipt of promised payment{f' of ${c.amount:,.2f}' if c.amount else ''}",
                                          owner="Collector", due_date=check.isoformat()))
        if dispute:
            actions.append(FollowUpAction(action="Open dispute case and send supporting documentation to Disputes Team",
                                          owner="Disputes Team", due_date=(call_date + timedelta(days=2)).isoformat()))
        if outcome == "Payment Made":
            actions.append(FollowUpAction(action="Confirm payment posting and apply cash to open invoices",
                                          owner="Billing", due_date=(call_date + timedelta(days=2)).isoformat()))
        if outcome in ("Callback Requested", "No Resolution", "Refused to Pay"):
            actions.append(FollowUpAction(action="Follow-up call with customer", owner="Collector",
                                          due_date=(call_date + timedelta(days=2)).isoformat()))

        inv_text = ", ".join(invoices) if invoices else "open invoices"
        summary_parts = [f"{customer_name} was contacted regarding {inv_text}."]
        if dispute:
            summary_parts.append("The customer disputed charges on the account.")
        if commitments:
            c = commitments[0]
            summary_parts.append(
                "The customer committed to pay"
                + (f" ${c.amount:,.2f}" if c.amount else "")
                + (f" by {c.due_date}" if c.due_date else "")
                + (f" via {c.method}" if c.method else "") + "."
            )
        if outcome == "Payment Made":
            summary_parts.append("The customer stated that payment has already been sent.")
        if not commitments and not dispute and outcome != "Payment Made":
            summary_parts.append("No payment commitment was obtained during the call.")
        summary_parts.append(f"Overall customer sentiment was {sentiment.lower()}; outcome recorded as {outcome}.")

        notes = [f"- Spoke with {customer_name} on {call_date.isoformat()} re: {inv_text}."]
        notes += [f"- RISK ({r.category}): {r.description}" for r in risks]
        notes += [
            f"- PTP: {'$' + format(c.amount, ',.2f') if c.amount else 'amount TBC'}"
            f" by {c.due_date or 'date TBC'}{' via ' + c.method if c.method else ''} ({c.confidence} confidence)."
            for c in commitments
        ]
        notes += [f"- NEXT: {a.action} ({a.owner}, due {a.due_date})." for a in actions]

        return CallAnalysis(
            call_log_summary=" ".join(summary_parts),
            interaction_notes="\n".join(notes),
            sentiment=sentiment,
            sentiment_score=score,
            call_outcome=outcome,
            dispute_raised=dispute,
            payment_commitments=commitments,
            risks=risks,
            follow_up_actions=actions,
        )


def _claude_available() -> bool:
    s = get_settings()
    return bool(s.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def analyze_transcript(transcript: str, call_date: date, customer_name: str) -> tuple[CallAnalysis, str]:
    """Returns the analysis and the label of the engine that produced it."""
    s = get_settings()
    use_claude = s.ai_engine == "claude" or (s.ai_engine == "auto" and _claude_available())
    if use_claude:
        try:
            result = ClaudeAnalyzer(s.anthropic_model, s.anthropic_api_key).analyze(transcript, call_date, customer_name)
            return result, f"claude:{s.anthropic_model}"
        except AnalysisError as exc:
            if s.ai_engine == "claude":
                raise
            log.warning("Claude analysis failed, falling back to rule-based analyzer: %s", exc)
    return RuleBasedAnalyzer().analyze(transcript, call_date, customer_name), "rules"
