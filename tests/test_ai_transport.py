"""E03-A2 bounded AI transport tests."""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch

from pullraptor.ai_adapter import request_ai_proposals_via_transport
from pullraptor.ai_context import ContextSelection
from pullraptor.ai_transport import (
    AIBudget,
    InertHttpsConnector,
    ProviderPolicy,
    TransportSendRecord,
    ignore_ambient_proxy_environment,
    invoke_provider,
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


class TestAITransport(unittest.TestCase):
    def setUp(self) -> None:
        self.selection = ContextSelection(("ctx",), b"hello context", "ok", "")
        self.policy = ProviderPolicy(
            profile="remote",
            approved_origin="https://api.example.com",
            approved_path="/v1/chat/completions",
            permitted_addresses=("93.184.216.34",),
            credential_reference="token-ref",
            spend_cap=None,
            retention_policy="operator_defined",
        )
        self.budget = AIBudget(
            max_requests=2,
            context_bytes=65_536,
            output_tokens=2048,
            deadline_seconds=60.0,
            started_at=time.monotonic(),
        )

    def test_proxy_environment_ignored(self) -> None:
        self.assertIn("HTTPS_PROXY", ignore_ambient_proxy_environment())
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://evil.proxy:8080", "HTTP_PROXY": "http://evil.proxy:8080"}):
            record = TransportSendRecord()
            connector = InertHttpsConnector(connected_host="93.184.216.34", record=record)
            result = invoke_provider(
                self.selection,
                self.policy,
                self.budget,
                credential="secret",
                connector=connector,
                send_record=record,
            )
        self.assertEqual(result.state, "ok")
        self.assertTrue(record.sent_credentials)

    def test_transport_no_ambient_proxy(self) -> None:
        self.test_proxy_environment_ignored()

    def test_redirect_not_followed(self) -> None:
        record = TransportSendRecord()
        connector = InertHttpsConnector(
            connected_host="93.184.216.34",
            status=302,
            response_body=b"",
            record=record,
        )
        result = invoke_provider(
            self.selection,
            self.policy,
            self.budget,
            credential="secret",
            connector=connector,
            send_record=record,
        )
        self.assertEqual(result.state, "transport_denied")
        self.assertEqual(result.cause, "redirect_not_followed")

    def test_transport_redirect_denied(self) -> None:
        self.test_redirect_not_followed()

    def test_actual_address_mismatch_denied(self) -> None:
        record = TransportSendRecord()
        connector = InertHttpsConnector(connected_host="1.1.1.1", record=record)
        result = invoke_provider(
            self.selection,
            self.policy,
            self.budget,
            credential="secret",
            connector=connector,
            send_record=record,
        )
        self.assertEqual(result.state, "transport_denied")
        self.assertEqual(record.sent_context_bytes, 0)
        self.assertFalse(record.sent_credentials)

    def test_transport_rebound_address_denied_before_send(self) -> None:
        self.test_actual_address_mismatch_denied()

    def test_remote_private_address_denied(self) -> None:
        record = TransportSendRecord()
        connector = InertHttpsConnector(connected_host="127.0.0.1", record=record)
        result = invoke_provider(
            self.selection,
            self.policy,
            self.budget,
            connector=connector,
            send_record=record,
        )
        self.assertEqual(result.state, "transport_denied")
        self.assertEqual(record.sent_context_bytes, 0)

    def test_explicit_local_profile(self) -> None:
        local_policy = ProviderPolicy(
            profile="local",
            approved_origin="https://127.0.0.1:8443",
            approved_path="/v1/chat",
            permitted_addresses=("127.0.0.1",),
            credential_reference="local",
            spend_cap=None,
            retention_policy="local_only",
        )
        record = TransportSendRecord()
        connector = InertHttpsConnector(connected_host="127.0.0.1", record=record)
        result = invoke_provider(
            self.selection,
            local_policy,
            self.budget,
            credential="local-token",
            connector=connector,
            send_record=record,
        )
        self.assertEqual(result.state, "ok")
        self.assertGreater(record.sent_context_bytes, 0)

    def test_retries_share_budget(self) -> None:
        record = TransportSendRecord()
        attempts = {"n": 0}

        class FlakyConnector(InertHttpsConnector):
            def post(self, url, body, headers, *, timeout):
                attempts["n"] += 1
                if attempts["n"] == 1:
                    return 503, b""
                return super().post(url, body, headers, timeout=timeout)

        connector = FlakyConnector(connected_host="93.184.216.34", record=record)
        result = invoke_provider(
            self.selection,
            self.policy,
            self.budget,
            connector=connector,
            send_record=record,
            retry_on_failure=lambda: True,
        )
        self.assertEqual(result.receipt.requests_used, 2)
        self.assertGreater(result.receipt.context_bytes, len(self.selection.serialized_bytes))

    def test_shared_budget_retry_exhaustion(self) -> None:
        self.test_retries_share_budget()

    def test_output_authority_fields_rejected(self) -> None:
        record = TransportSendRecord()
        body = b'{"choices":[{"message":{"content":"x","permission":"admin"}}]}'
        connector = InertHttpsConnector(connected_host="93.184.216.34", response_body=body, record=record)
        result = invoke_provider(
            self.selection,
            self.policy,
            self.budget,
            connector=connector,
            send_record=record,
        )
        self.assertEqual(result.state, "unavailable")
        self.assertEqual(result.cause, "authority_field_rejected")

    def test_ai_authority_fields_rejected(self) -> None:
        self.test_output_authority_fields_rejected()

    def test_response_byte_depth_item_limits(self) -> None:
        huge = b"x" * (1_048_577)
        record = TransportSendRecord()
        connector = InertHttpsConnector(connected_host="93.184.216.34", response_body=huge, record=record)
        result = invoke_provider(
            self.selection,
            self.policy,
            self.budget,
            connector=connector,
            send_record=record,
        )
        self.assertEqual(result.cause, "response_too_large")

    def test_provider_unavailable_preserves_report(self) -> None:
        span = Span("a.py", "head", 1, 1, 0, 1, 1, 1)
        finding = Finding(
            rule="PY001",
            version="1",
            obligation="x",
            anchor="a",
            span=span,
            claim="c",
            severity="advisory",
            policy_class="advisory",
            state="supported",
            witness="w",
        )
        contract = ReviewContract(
            base_tip="b",
            comparison_base="b",
            head="h",
            policy_digest="p",
            config_digest="c",
            tool_digest="t",
            profile="structural",
            expected_scope=(),
            discovery_complete=True,
        )
        report = FullReport(
            schema="1",
            kind="full",
            contract=contract,
            receipts=(),
            findings=(finding,),
            diagnostics=(),
            execution={"exit_code": 0},
        )
        limits = RecordLimits()
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)
        before = canonical_bytes(report, limits=limits, deadline=deadline)
        record = TransportSendRecord()
        connector = InertHttpsConnector(connected_host="93.184.216.34", status=500, record=record)
        invoke_provider(
            self.selection,
            self.policy,
            self.budget,
            connector=connector,
            send_record=record,
        )
        after = canonical_bytes(report, limits=limits, deadline=deadline)
        self.assertEqual(before, after)

    def test_two_requests_output_tokens_per_request(self) -> None:
        record = TransportSendRecord()
        connector = InertHttpsConnector(connected_host="93.184.216.34", record=record)
        tight = AIBudget(2, 200_000, 2048, 60.0, time.monotonic())
        result = invoke_provider(self.selection, self.policy, tight, connector=connector, send_record=record)
        self.assertEqual(result.receipt.requested_output_tokens, 2048)

    def test_retry_aggregate_context_deadline_exhaustion(self) -> None:
        record = TransportSendRecord()
        connector = InertHttpsConnector(connected_host="93.184.216.34", record=record)
        tiny = AIBudget(2, 10, 2048, 60.0, time.monotonic())
        result = invoke_provider(self.selection, self.policy, tiny, connector=connector, send_record=record)
        self.assertEqual(result.state, "budget_exhausted")
        self.assertEqual(result.cause, "context_budget_exhausted")

    def test_request_ai_proposals_via_transport_wrapper(self) -> None:
        record = TransportSendRecord()
        connector = InertHttpsConnector(connected_host="93.184.216.34", record=record)
        result = request_ai_proposals_via_transport(
            self.selection,
            self.policy,
            self.budget,
            connector=connector,
            send_record=record,
        )
        self.assertEqual(result.state, "ok")
        self.assertEqual(len(result.proposals), 1)


if __name__ == "__main__":
    unittest.main()
