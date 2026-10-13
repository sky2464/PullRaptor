"""Behavioral regressions for the trusted E02-A2 publication boundary."""
from dataclasses import replace
import unittest
import json
import hashlib
from pathlib import Path
from unittest.mock import patch

from pullraptor.models import CoverageReceipt, ScopeEntry, Span
from pullraptor.publication_contract import PublicationContext, PublicationRange, scope_digest_from_scope, validate_publication
from pullraptor.publisher import publish_report
from tests.test_publication_contract import _full_report, _context_for_report, _UNIT_SCOPES
from tests.test_publication_binding_fixtures import _finding, _scoped_report
from tests.test_publisher import _report_dict, _CONNECTOR, _pr_payload, _expected_context, _trusted_current


class TestE02Closure(unittest.TestCase):
    def test_scope_null_empty_and_delimiters_are_distinct(self):
        entry = ScopeEntry(key='key', kind='file', snapshot='tree', capability='diff')
        pairs = [
            (entry, replace(entry, path='')),
            (replace(entry, key='a|b', kind='c'), replace(entry, key='a', kind='b|c')),
            (entry, replace(entry, path_bytes=b'')),
        ]
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertNotEqual(scope_digest_from_scope((left,)), scope_digest_from_scope((right,)))

    def test_scope_digest_covers_all_fields_and_is_order_independent(self):
        entry = ScopeEntry(key='first', kind='file', snapshot='tree', capability='diff')
        baseline = scope_digest_from_scope((entry,))
        changes = {'key': 'other', 'kind': 'lookup', 'snapshot': 'other', 'capability': 'other',
                   'path_bytes': b'a|b\nc', 'path': 'a|b\nc', 'source_occurrence': 'occurrence',
                   'canonical_target': 'target', 'relative_level': 0, 'reason': 'changed'}
        for field, value in changes.items():
            with self.subTest(field=field):
                self.assertNotEqual(baseline, scope_digest_from_scope((replace(entry, **{field: value}),)))
        second = replace(entry, key='second')
        self.assertEqual(scope_digest_from_scope((entry, second)), scope_digest_from_scope((second, entry)))

    def test_missing_identity_and_bad_base_or_digest_denied(self):
        report = _full_report()
        context = _context_for_report(report)
        for field, value in [('workflow_id', ''), ('repository_id', ''), ('pr_number', 0),
                             ('base_tip', 'deadbeef'), ('comparison_base', ''),
                             ('artifact_digest', 'not-a-sha'), ('reviewer_digest', '')]:
            with self.subTest(field=field):
                bad = replace(context, **{field: value})
                self.assertFalse(validate_publication(report, bad, bad, actual_report_digest="f" * 64).authorized)

    def test_report_tool_and_config_cannot_choose_authority(self):
        original = _full_report()
        context = _context_for_report(original)
        for field in ['tool_digest', 'config_digest', 'profile']:
            report = replace(original, contract=replace(original.contract, **{field: 'tampered'}))
            with self.subTest(field=field):
                self.assertFalse(validate_publication(report, context, context, actual_report_digest="f" * 64).authorized)

    def test_invalid_or_out_of_diff_lines_denied(self):
        for start, end in [(99, 99), (1, 99)]:
            report = _full_report(findings=(replace(_finding(), span=Span('app.py', 'head', start, end, 0, 1, 1, 2)),))
            context = _context_for_report(report)
            with self.subTest(start=start, end=end):
                self.assertFalse(validate_publication(report, context, context, actual_report_digest="f" * 64).authorized)

    def test_receipt_gap_status_and_duplicate_scope_denied(self):
        report = _scoped_report()
        entry = report.contract.expected_scope[0]
        receipt = CoverageReceipt(entry.key, "policy-a", entry.capability, "complete")
        complete = replace(report, receipts=(receipt,))
        cases = [replace(complete, receipts=(replace(receipt, status="gap"),)),
                 replace(complete, contract=replace(complete.contract, expected_scope=(entry, entry)))]
        for index, case in enumerate(cases):
            with self.subTest(case=index):
                context = _context_for_report(case, scope_digest=_UNIT_SCOPES["duplicate_file_scope" if index else "file_scope"])
                decision = validate_publication(case, context, context, actual_report_digest="f" * 64)
                self.assertFalse(decision.authorized)
                self.assertEqual(decision.cause, "incomplete_receipts")

    @patch('pullraptor.publisher._github_api_request')
    def test_report_cannot_supply_missing_connector_authority(self, api):
        api.side_effect = [(200, _pr_payload()), (200, []), (200, _pr_payload()), (201, {'id': 1})]
        code = publish_report(_report_dict(), 'owner/repo', 1, 'inert', connector=_CONNECTOR)
        self.assertEqual(code, 2)
        self.assertFalse(any(c.kwargs.get('method') in ('POST', 'PATCH') for c in api.call_args_list))

    @patch('pullraptor.publisher._github_api_request')
    def test_exact_report_bytes_are_required_even_when_json_is_equal(self, api):
        raw = (Path(__file__).parent / 'fixtures/e02/publisher/trusted-report.json').read_bytes()
        for candidate in (None, raw + b' ', raw.replace(b'pol1', b'evil')):
            with self.subTest(candidate=candidate):
                api.reset_mock()
                api.return_value = (200, _pr_payload())
                code = publish_report(_report_dict(), 'owner/repo', 1, 'inert',
                                      expected_context=_expected_context(), raw_report_bytes=candidate,
                                      current_authority=_trusted_current)
                self.assertEqual(code, 2)
                self.assertFalse(any(c.kwargs.get('method') in ('POST', 'PATCH') for c in api.call_args_list))

    @patch('pullraptor.publisher._github_api_request')
    def test_exact_trusted_inline_fixture_can_publish(self, api):
        root = Path(__file__).parent / 'fixtures/e02'
        raw = (root / 'publisher/trusted-inline-report.json').read_bytes()
        fields = json.loads((root / 'publication-binding/trusted-inline-authority.json').read_bytes())
        fields['permitted_ranges'] = tuple(PublicationRange(**item) for item in fields['permitted_ranges'])
        context = PublicationContext(**fields)
        api.side_effect = [(200, _pr_payload()), (200, []), (200, _pr_payload()), (201, {'id': 21})]
        code = publish_report(json.loads(raw), 'owner/repo', 1, 'inert', expected_context=context,
                              raw_report_bytes=raw, current_authority=lambda pr: context)
        self.assertEqual(code, 0)
        self.assertEqual(sum(c.kwargs.get('method') == 'POST' for c in api.call_args_list), 1)

    @patch('pullraptor.publisher._github_api_request')
    def test_bool_and_string_inline_coordinates_are_not_coerced(self, api):
        root = Path(__file__).parent / 'fixtures/e02'
        report = json.loads((root / 'publisher/trusted-inline-report.json').read_bytes())
        fields = json.loads((root / 'publication-binding/trusted-inline-authority.json').read_bytes())
        fields['permitted_ranges'] = tuple(PublicationRange(**item) for item in fields['permitted_ranges'])
        for value in (True, '1'):
            with self.subTest(value=value):
                api.reset_mock()
                api.side_effect = [(200, _pr_payload()), (200, []), (200, _pr_payload()), (201, {'id': 21})]
                report['findings'][0]['span']['start_line'] = value
                raw = json.dumps(report).encode()
                context = replace(PublicationContext(**fields), report_digest=hashlib.sha256(raw).hexdigest())
                code = publish_report(report, 'owner/repo', 1, 'inert', expected_context=context,
                                      raw_report_bytes=raw, current_authority=lambda pr: context)
                self.assertEqual(code, 3)
                self.assertEqual(api.call_count, 0)

    @patch('pullraptor.publisher._github_api_request')
    def test_missing_side_cannot_default_to_head(self, api):
        root = Path(__file__).parent / 'fixtures/e02'
        report = json.loads((root / 'publisher/trusted-inline-report.json').read_bytes())
        fields = json.loads((root / 'publication-binding/trusted-inline-authority.json').read_bytes())
        fields['permitted_ranges'] = tuple(PublicationRange(**item) for item in fields['permitted_ranges'])
        del report['findings'][0]['span']['side']
        raw = json.dumps(report).encode()
        context = replace(PublicationContext(**fields), report_digest=hashlib.sha256(raw).hexdigest())
        api.side_effect = [(200, _pr_payload()), (200, []), (200, _pr_payload()), (201, {'id': 21})]
        code = publish_report(report, 'owner/repo', 1, 'inert', expected_context=context,
                              raw_report_bytes=raw, current_authority=lambda pr: context)
        self.assertEqual(code, 3)
        self.assertEqual(api.call_count, 0)

    def test_customer_beta_publisher_remains_disabled(self):
        from pullraptor.publisher import main
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(main([]), 2)

    @patch('pullraptor.publisher._github_api_request')
    def test_each_retry_rechecks_all_connector_authority(self, api):
        raw = (Path(__file__).parent / 'fixtures/e02/publisher/trusted-report.json').read_bytes()
        changes = {'head': 'f'*40, 'base_tip': 'f'*40, 'comparison_base': 'f'*40,
                   'policy_digest': 'changed', 'scope_digest': 'f'*64, 'tool_digest': 'changed',
                   'config_digest': 'changed', 'reviewer_digest': 'f'*64, 'artifact_digest': 'f'*64,
                   'run_id': 'changed', 'workflow_id': 'changed', 'report_digest': 'f'*64,
                   'permitted_ranges': (), 'profile': 'diff', 'repository_id': 'other/repo',
                   'pr_number': 2}
        for method in ('POST', 'PATCH'):
            for field, value in changes.items():
                with self.subTest(method=method, field=field):
                    authority_reads = 0
                    writes = []
                    context = _expected_context()
                    def current(pr):
                        nonlocal authority_reads
                        authority_reads += 1
                        return context if authority_reads <= 2 else replace(context, **{field: value})
                    inventory_reads = 0
                    def request(url, token, method='GET', payload=None):
                        nonlocal inventory_reads
                        if method in ('POST', 'PATCH'):
                            writes.append(method)
                            raise RuntimeError('inert transient failure')
                        if 'comments' in url:
                            inventory_reads += 1
                            if inventory_reads == 1:
                                return 200, ([{'id': 77, 'body': '<!-- pullraptor:review -->',
                                               'user': {'login': 'pullraptor-bot'}}] if target == 'PATCH' else [])
                            return 200, []
                        return 200, _pr_payload()
                    target = method
                    api.side_effect = request
                    api.reset_mock()
                    code = publish_report(json.loads(raw), 'owner/repo', 1, 'inert', expected_context=context,
                                          raw_report_bytes=raw, current_authority=current)
                    self.assertEqual(code, 2)
                    self.assertEqual(writes, [method])
                    self.assertEqual(authority_reads, 3)

    @patch('pullraptor.publisher._github_api_request')
    def test_unavailable_authority_denies_before_first_write(self, api):
        api.return_value = (200, _pr_payload())
        def unavailable(pr):
            raise RuntimeError('connector unavailable')
        code = publish_report(_report_dict(), 'owner/repo', 1, 'inert', expected_context=_expected_context(),
                              raw_report_bytes=json.dumps(_report_dict()).encode(), current_authority=unavailable)
        self.assertEqual(code, 2)
        self.assertEqual(api.call_count, 1)


if __name__ == '__main__':
    unittest.main()
