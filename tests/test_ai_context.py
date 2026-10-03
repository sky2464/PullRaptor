"""E03-A1 context manifest selection tests."""

from __future__ import annotations

import json
import unittest

from pullraptor.ai_context import (
    ContextBlock,
    ContextManifest,
    block_digest,
    injected_config_inert,
    preview_context,
    select_context,
)


class TestAIContext(unittest.TestCase):
    def _block(
        self,
        block_id: str,
        *,
        kind: str = "issue",
        mandatory: bool = False,
        priority: int = 0,
        payload: bytes = b"x",
        source_revision: str = "rep1",
    ) -> ContextBlock:
        return ContextBlock(
            id=block_id,
            kind=kind,
            producer="fixture",
            source_revision=source_revision,
            digest=block_digest(payload),
            serialized_bytes=payload,
            mandatory=mandatory,
            priority=priority,
        )

    def test_stale_ci_log_rejected(self) -> None:
        block = self._block("ci", kind="ci_log", payload=b"log", source_revision="headA")
        manifest = ContextManifest(
            report_digest="rep1",
            head="headB",
            blocks=(block,),
            retrieval_receipts=(json.dumps({"head": "headA", "run": 1}),),
        )
        selection = select_context(manifest, 65_536)
        self.assertEqual(selection.state, "unavailable")

    def test_issue_revision_bound(self) -> None:
        block = self._block("issue", kind="issue", payload=b"issue", source_revision="wrong")
        manifest = ContextManifest("rep1", "head1", (block,), ())
        selection = select_context(manifest, 65_536)
        self.assertEqual(selection.block_ids, ())

    def test_mandatory_guard_over_budget_abstains(self) -> None:
        big = b"a" * 65_537
        block = self._block("guard", mandatory=True, priority=0, payload=big, source_revision="rep1")
        manifest = ContextManifest("rep1", "head1", (block,), ())
        selection = select_context(manifest, 65_536)
        self.assertEqual(selection.state, "unavailable")
        self.assertEqual(selection.cause, "mandatory_context_over_budget")
        self.assertEqual(selection.serialized_bytes, b"")

    def test_utf8_serialized_cost_exact(self) -> None:
        payload = "café".encode("utf-8")
        block = self._block("u", payload=payload, source_revision="rep1")
        manifest = ContextManifest("rep1", "head1", (block,), ())
        selection = select_context(manifest, 65_536)
        self.assertEqual(selection.serialized_bytes, payload)
        self.assertEqual(len(selection.serialized_bytes), 5)

    def test_context_preview_redacted(self) -> None:
        from pullraptor.ai_context import ContextSelection

        selection = ContextSelection(("a",), b"token ghp_" + b"1" * 36, "ok", "")
        preview = preview_context(selection)
        self.assertIn("[REDACTED]", preview)
        self.assertNotIn("ghp_", preview)

    def test_injected_config_inert(self) -> None:
        self.assertTrue(injected_config_inert('{"model":"x"}'))
        self.assertFalse(injected_config_inert('{"permission":"admin"}'))


if __name__ == "__main__":
    unittest.main()
