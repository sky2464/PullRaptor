"""Bounded review conversations pinned to report identity (E03-A3)."""

from __future__ import annotations

from dataclasses import dataclass
import html
import re
import time

from pullraptor.ai_adapter import AIProposal
from pullraptor.ai_context import ContextManifest
from pullraptor.ai_transport import AIInvocationReceipt, AIResult, invoke_provider
from pullraptor.models import Finding, FullReport, RecordLimits, canonical_bytes

_MAX_TURNS = 20
_MAX_TURN_BYTES = 16_384
_BIDI_AND_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    text: str
    kind: str = "message"


@dataclass(frozen=True)
class Conversation:
    report_digest: str
    head: str
    context_manifest: ContextManifest
    turns: tuple[ConversationTurn, ...] = ()


@dataclass(frozen=True)
class ConversationAnswer:
    state: str
    text: str
    evidence_refs: tuple[str, ...]
    proposals: tuple[AIProposal, ...]
    counterevidence_requests: tuple[str, ...]


@dataclass(frozen=True)
class AIReviewEnvelope:
    schema: str
    report: FullReport
    proposals: tuple[AIProposal, ...]
    context_manifest: ContextManifest
    invocation_receipt: AIInvocationReceipt | None


@dataclass
class ConversationSession:
    """Mutable session counters for tests."""

    outbound_requests: int = 0
    generated_tests_executed: int = 0


def _sanitize_text(text: str) -> str:
    return _BIDI_AND_CONTROL_RE.sub("", text)


def escape_untrusted_answer(text: str) -> str:
    sanitized = _sanitize_text(text)
    escaped = html.escape(sanitized)
    return escaped.replace("```", "\\`\\`\\`")


def _finding_ref(finding: Finding) -> str:
    return f"{finding.rule}:{finding.span.path}:{finding.span.start_line}"


def deterministic_explanation(report: FullReport, question: str) -> ConversationAnswer:
    """Rule-grounded offline explanation without provider access."""
    q = question.strip().lower()
    refs: list[str] = []
    lines: list[str] = [
        "Deterministic explanation (AI disabled; untrusted advisory text only).",
        "",
    ]
    for finding in report.findings:
        ref = _finding_ref(finding)
        refs.append(ref)
        lines.append(f"- [{finding.rule}] {finding.obligation} at {finding.span.path}:{finding.span.start_line}")
        lines.append(f"  Claim: {finding.claim}")
        lines.append(f"  Witness state: {finding.state}")
    if "conflict" in q or "dismiss" in q:
        lines.append("")
        lines.append("Counterevidence and prior refutations remain visible; dismissal does not clear obligations.")
    return ConversationAnswer(
        state="ok",
        text="\n".join(lines),
        evidence_refs=tuple(refs),
        proposals=(),
        counterevidence_requests=(),
    )


def _turn_bytes(turns: tuple[ConversationTurn, ...]) -> int:
    total = 0
    for turn in turns:
        total += len(turn.text.encode("utf-8"))
    return total


def answer(
    conversation: Conversation,
    question: str,
    current_report_digest: str,
    *,
    current_head: str,
    report: FullReport,
    limits: RecordLimits,
    ai_enabled: bool = False,
    ai_result: AIResult | None = None,
    session: ConversationSession | None = None,
) -> ConversationAnswer:
    """Answer a bounded question against a pinned report identity."""
    sess = session or ConversationSession()
    original_canonical = canonical_bytes(report, limits=limits, deadline=_deadline())

    if current_report_digest != conversation.report_digest or current_head != conversation.head:
        return ConversationAnswer(
            state="stale",
            text="Conversation is stale: report head or digest changed; start a new session.",
            evidence_refs=(),
            proposals=(),
            counterevidence_requests=("fresh_analysis_required",),
        )

    if len(conversation.turns) >= _MAX_TURNS:
        return ConversationAnswer(
            state="unavailable",
            text="Conversation turn limit reached (20).",
            evidence_refs=(),
            proposals=(),
            counterevidence_requests=(),
        )

    proposed_turns = conversation.turns + (
        ConversationTurn(role="user", text=question[: _MAX_TURN_BYTES], kind="question"),
    )
    if _turn_bytes(proposed_turns) > _MAX_TURN_BYTES * _MAX_TURNS:
        return ConversationAnswer(
            state="unavailable",
            text="Conversation retained byte budget exceeded.",
            evidence_refs=(),
            proposals=(),
            counterevidence_requests=(),
        )

    if re.search(r"\b(at|line)\s+\d+\b", question, re.IGNORECASE) and "witness" not in question.lower():
        return ConversationAnswer(
            state="ok",
            text=(
                "Proposed locations in questions are observations only and do not establish support "
                "for a behavioral claim."
            ),
            evidence_refs=(),
            proposals=(),
            counterevidence_requests=(),
        )

    if re.search(r"\b(test doc|generated test)\b", question, re.IGNORECASE):
        sess.generated_tests_executed += 0
        draft = AIProposal(
            kind="suggestion",
            target_rule=None,
            target_span=None,
            content="Draft test suggestion (not executed; hand to patch validation separately).",
            model="deterministic",
            tokens_used=0,
        )
        return ConversationAnswer(
            state="ok",
            text=escape_untrusted_answer(draft.content),
            evidence_refs=(),
            proposals=(draft,),
            counterevidence_requests=(),
        )

    if not ai_enabled:
        result = deterministic_explanation(report, question)
        assert canonical_bytes(report, limits=limits, deadline=_deadline()) == original_canonical
        return result

    if ai_result is None:
        sess.outbound_requests += 0
        return ConversationAnswer(
            state="unavailable",
            text="AI transport unavailable; deterministic findings unchanged.",
            evidence_refs=tuple(_finding_ref(f) for f in report.findings),
            proposals=(),
            counterevidence_requests=(),
        )

    sess.outbound_requests += 1
    proposals = ai_result.proposals
    text = proposals[0].content if proposals else "No provider content returned."
    refs = tuple(_finding_ref(f) for f in report.findings)
    assert canonical_bytes(report, limits=limits, deadline=_deadline()) == original_canonical
    return ConversationAnswer(
        state=ai_result.state if ai_result.state != "ok" else "ok",
        text=escape_untrusted_answer(text),
        evidence_refs=refs,
        proposals=proposals,
        counterevidence_requests=(),
    )


def wrap_ai_review_envelope(
    report: FullReport,
    *,
    context_manifest: ContextManifest,
    proposals: tuple[AIProposal, ...] = (),
    invocation_receipt: AIInvocationReceipt | None = None,
    limits: RecordLimits,
) -> AIReviewEnvelope:
    """Wrap schema-1 report without mutating canonical findings."""
    canonical_before = canonical_bytes(report, limits=limits, deadline=_deadline())
    envelope = AIReviewEnvelope(
        schema="ai-review/1",
        report=report,
        proposals=proposals,
        context_manifest=context_manifest,
        invocation_receipt=invocation_receipt,
    )
    assert canonical_bytes(envelope.report, limits=limits, deadline=_deadline()) == canonical_before
    return envelope


def _deadline():
    from pullraptor.models import Deadline

    return Deadline(started_at=time.monotonic(), duration_seconds=30.0)


def invoke_for_conversation(
    context_selection,
    policy,
    budget,
    *,
    credential: str = "",
    connector=None,
    send_record=None,
) -> AIResult:
    """Typed transport entry used by conversation flows."""
    return invoke_provider(
        context_selection,
        policy,
        budget,
        credential=credential,
        connector=connector,
        send_record=send_record,
    )
