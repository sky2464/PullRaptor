"""Tests for local secret pattern scanning (E05-A3 construction)."""

from __future__ import annotations

import io
import logging
import time
import unittest

from pullraptor.render import render_markdown
from pullraptor.models import Deadline, FullReport, RecordLimits, ReviewContract
from pullraptor.secret_patterns import DEFAULT_PATTERNS, scan_secrets


def _high_entropy_token(length: int = 48) -> str:
    alphabet = "0123456789abcdef"
    return "".join(alphabet[i % len(alphabet)] for i in range(length))


class TestSecretPatterns(unittest.TestCase):
    def test_secret_never_in_report_log_cache(self) -> None:
        token = "a" * 48
        source = f'api_key = "{token}"\n'.encode()
        observations = scan_secrets(source)
        self.assertTrue(observations)
        joined = " ".join(
            obs.redacted_label for obs in observations
        )
        self.assertNotIn(token, joined)
        for obs in observations:
            self.assertNotIn(token, obs.redacted_label)

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger("pullraptor.test.secrets")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.info("scan found %s", observations[0].redacted_label)
        logger.removeHandler(handler)
        self.assertNotIn(token, log_stream.getvalue())

        report = FullReport(
            schema="1",
            kind="full",
            contract=ReviewContract(
                base_tip="b" * 40,
                comparison_base="c" * 40,
                head="h" * 40,
                policy_digest="p",
                config_digest="cfg",
                tool_digest="tool",
                profile="structural",
                expected_scope=(),
                discovery_complete=True,
            ),
            receipts=(),
            inventory=(),
            findings=(),
            diagnostics=(),
            execution={"exit_code": 0},
        )
        md = render_markdown(
            report,
            limits=RecordLimits(),
            deadline=Deadline(started_at=time.monotonic(), duration_seconds=60.0),
        )
        self.assertNotIn(token, md)

    def test_examples_and_placeholders_advisory(self) -> None:
        source = b'api_key = "example_api_key_placeholder_not_real_credential_123456"\n'
        observations = scan_secrets(source, DEFAULT_PATTERNS)
        secret002 = [obs for obs in observations if obs.pattern_id == "SECRET002"]
        self.assertTrue(secret002)
        self.assertIn("REDACTED", secret002[0].redacted_label)

    def test_high_entropy_not_verified_credential(self) -> None:
        token = _high_entropy_token(48)
        source = f"access_token: {token}\n".encode()
        observations = scan_secrets(source)
        entropy_hits = [obs for obs in observations if obs.pattern_id == "SECRET003"]
        self.assertTrue(entropy_hits)
        self.assertIn("ENTROPY", entropy_hits[0].redacted_label)

    def test_unicode_location(self) -> None:
        prefix = "ключ_api".encode("utf-8")
        source = prefix + b' = "' + b"a" * 40 + b'"\n'
        observations = scan_secrets(source)
        self.assertEqual(observations, ())

        marker = "-----BEGIN PRIVATE KEY-----".encode("utf-8")
        source = "префикс ".encode("utf-8") + marker
        observations = scan_secrets(source)
        self.assertEqual(len(observations), 1)
        self.assertGreater(observations[0].relative_span.start_byte, 0)

    def test_no_remote_probe(self) -> None:
        import pullraptor.secret_patterns as module

        self.assertFalse(hasattr(module, "socket"))
        source = b'client_secret="0123456789abcdef0123456789abcdef0123456789"\n'
        observations = scan_secrets(source)
        self.assertTrue(observations)


if __name__ == "__main__":
    unittest.main()
