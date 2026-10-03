"""E03-A3 conversation and envelope tests."""

from __future__ import annotations

import hashlib
import time
import unittest

from pullraptor.ai_context import ContextManifest
from pullraptor.ai_transport import AIInvocationReceipt, AIResult
from pullraptor.conversation import (
    AIReviewEnvelope,
    Conversation,
    ConversationSession,
    ConversationTurn,
    answer,
    deterministic_explanation,
    escape_untrusted_answer,
    wrap_ai_review_envelope,
)
from pullraptor.models import (
    Deadline,
    Finding,
    FullReport,
    RecordLimits,
    ReviewContract,
    Span,
    canonical_bytes,
)
from pullraptor.render import render_markdown


class TestConversation(unittest.TestCase):
    def setUp(self) -> None:
        self.span = Span("src/vuln.py", "head", 10, 10, 100, 150, 1, 50)
        self.finding = Finding(
            rule="PY001",
            version="1.0.0",
            obligation="subprocess.call.shell_injection",
            anchor="call_eval",
            span=self.span,
            claim="Call uses shell=True",
            severity="advisory",
            policy_class="advisory",
            state="supported",
            witness="subprocess.call(user_input, shell=True)",
        )
        self.contract = ReviewContract(
            base_tip="b",
            comparison_base="b",
            head="head1",
            policy_digest="p",
            config_digest="c",
            tool_digest="t",
            profile="structural",
            expected_scope=(),
            discovery_complete=True,
        )
        self.report = FullReport(
            schema="1",
            kind="full",
            contract=self.contract,
            receipts=(),
            findings=(self.finding,),
            diagnostics=(),
            execution={"exit_code": 0},
        )
        self.limits = RecordLimits()
        self.deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)
        self.digest = hashlib.sha256(
            canonical_bytes(self.report, limits=self.limits, deadline=self.deadline)
        ).hexdigest()
        self.manifest = ContextManifest(self.digest, "head1", (), ())

    def _conversation(self, turns: tuple[ConversationTurn, ...] = ()) -> Conversation:
        return Conversation(
            report_digest=self.digest,
            head="head1",
            context_manifest=self.manifest,
            turns=turns,
        )

    def test_ai_disabled_no_network(self) -> None:
        session = ConversationSession()
        result = answer(
            self._conversation(),
            "Explain PY001",
            self.digest,
            current_head="head1",
            report=self.report,
            limits=self.limits,
            ai_enabled=False,
            session=session,
        )
        self.assertEqual(result.state, "ok")
        self.assertEqual(session.outbound_requests, 0)
        self.assertIn("PY001", result.text)

    def test_ai_disabled_deterministic_explanation(self) -> None:
        self.test_ai_disabled_no_network()

    def test_head_or_context_change_stale(self) -> None:
        session = ConversationSession()
        result = answer(
            self._conversation(),
            "Why?",
            self.digest,
            current_head="head2",
            report=self.report,
            limits=self.limits,
            ai_enabled=True,
            session=session,
        )
        self.assertEqual(result.state, "stale")
        self.assertEqual(session.outbound_requests, 0)

    def test_conversation_stale_no_outbound(self) -> None:
        self.test_head_or_context_change_stale()

    def test_conflict_preserved(self) -> None:
        result = deterministic_explanation(self.report, "dismiss this conflict")
        self.assertIn("Counterevidence", result.text)
        self.assertIn("does not clear", result.text)

    def test_conversation_counterevidence_preserved(self) -> None:
        self.test_conflict_preserved()

    def test_fake_location_not_supported(self) -> None:
        result = answer(
            self._conversation(),
            "The bug is at line 999",
            self.digest,
            current_head="head1",
            report=self.report,
            limits=self.limits,
        )
        self.assertIn("observations only", result.text)

    def test_test_doc_draft_not_executed(self) -> None:
        session = ConversationSession()
        result = answer(
            self._conversation(),
            "Write a generated test doc for this",
            self.digest,
            current_head="head1",
            report=self.report,
            limits=self.limits,
            session=session,
        )
        self.assertEqual(session.generated_tests_executed, 0)
        self.assertEqual(result.proposals[0].kind, "suggestion")

    def test_20_turn_limit(self) -> None:
        turns = tuple(
            ConversationTurn(role="user", text=f"q{i}", kind="question") for i in range(20)
        )
        result = answer(
            self._conversation(turns),
            "one more",
            self.digest,
            current_head="head1",
            report=self.report,
            limits=self.limits,
        )
        self.assertEqual(result.state, "unavailable")

    def test_conversation_turn_and_byte_caps(self) -> None:
        self.test_20_turn_limit()

    def test_canonical_findings_unchanged(self) -> None:
        before = canonical_bytes(self.report, limits=self.limits, deadline=self.deadline)
        envelope = wrap_ai_review_envelope(
            self.report,
            context_manifest=self.manifest,
            limits=self.limits,
        )
        after = canonical_bytes(envelope.report, limits=self.limits, deadline=self.deadline)
        self.assertEqual(before, after)

    def test_conversation_report_digest_unchanged(self) -> None:
        self.test_canonical_findings_unchanged()

    def test_envelope_preserves_schema1_report(self) -> None:
        envelope = wrap_ai_review_envelope(
            self.report,
            context_manifest=self.manifest,
            invocation_receipt=AIInvocationReceipt(0, 0, 0, 0.0, "cost_unknown"),
            limits=self.limits,
        )
        self.assertEqual(envelope.schema, "ai-review/1")
        self.assertEqual(envelope.report.schema, "1")

    def test_untrusted_answer_safe_render(self) -> None:
        escaped = escape_untrusted_answer("```<script>alert(1)</script>")
        self.assertNotIn("<script>", escaped)
        report = FullReport(
            schema="1",
            kind="full",
            contract=self.contract,
            receipts=(),
            findings=(self.finding,),
            diagnostics=(),
            execution={
                "exit_code": 0,
                "proposals": [{"kind": "explanation", "model": "m", "content": "<script>x</script>"}],
            },
        )
        md = render_markdown(report, limits=self.limits, deadline=self.deadline)
        self.assertNotIn("<script>", md)


if __name__ == "__main__":
    unittest.main()
