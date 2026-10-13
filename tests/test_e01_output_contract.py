"""Full output failures and hostile text retain scope and deterministic failure status."""
from dataclasses import replace
import io
import json
import time
import unittest
from unittest.mock import patch
from urllib.parse import unquote

from pullraptor.__main__ import main
from pullraptor.models import Deadline, Diagnostic, Finding, FullReport, LimitFailure, RecordLimits, ReviewContract, Span
from pullraptor.render import render_json, render_markdown, render_sarif

RENDERERS = (render_json, render_markdown, render_sarif)


def report(claim='A pattern', path='app.py', side='head', discovery=True):
    contract = ReviewContract(base_tip='b', comparison_base='b', head='h', policy_digest='p', config_digest='c',
                              tool_digest='t', profile='structural', expected_scope=(), discovery_complete=discovery)
    finding = Finding(rule='PY001', version='1.0', obligation='pattern', anchor='a',
                      span=Span(path, side, 1, 1, 0, 1, 1, 2), claim=claim, severity='advisory',
                      policy_class='advisory', state='supported', witness='x.append(1)')
    return FullReport(schema='1', kind='full', contract=contract, receipts=(), findings=(finding,),
                      diagnostics=(), execution={'exit_code': 0})


class OutputContractTests(unittest.TestCase):
    def test_all_formats_obey_report_byte_limit(self):
        for renderer in RENDERERS:
            with self.subTest(format=renderer.__name__):
                with self.assertRaises(ValueError):
                    renderer(report('x' * 20000), limits=RecordLimits(max_payload_bytes=16384),
                             deadline=Deadline(time.monotonic(), 30))

    def test_all_formats_obey_work_cutoff(self):
        deadline = Deadline(time.monotonic() - 2, 3)
        for renderer in RENDERERS:
            with self.subTest(format=renderer.__name__):
                with self.assertRaises(TimeoutError):
                    renderer(report(), limits=RecordLimits(), deadline=deadline)

    def test_all_formats_obey_report_item_limit(self):
        value = replace(report(), inventory=tuple(str(i) for i in range(130)))
        for renderer in RENDERERS:
            with self.subTest(format=renderer.__name__):
                with self.assertRaises(ValueError):
                    renderer(value, limits=RecordLimits(max_aggregate_items=128),
                             deadline=Deadline(time.monotonic(), 30))

    def test_markdown_visibly_escapes_controls_bidi_links_and_paths(self):
        value = report('\x1b[31m\r\u202e[evil](https://example.invalid)')
        value = replace(value, diagnostics=(Diagnostic('GAP', '[click](https://example.invalid)',
                                                      path='`\n<script>[evil](https://example.invalid)'),))
        text = render_markdown(value, limits=RecordLimits(), deadline=Deadline(time.monotonic(), 30))
        for active in ('\x1b', '\r', '\u202e', '<script>', '[evil](', '[click]('):
            self.assertNotIn(active, text)
        self.assertIn('\\u001b', text)
        self.assertIn('\\u202e', text)
        self.assertIn('\\r', text)

    def test_incomplete_discovery_not_rendered_complete(self):
        value = report(discovery=False)
        text = render_markdown(value, limits=RecordLimits(), deadline=Deadline(time.monotonic(), 30))
        self.assertNotIn('**Status:** Complete', text)
        self.assertIn('Partial', text)
        data = json.loads(render_sarif(value, limits=RecordLimits(), deadline=Deadline(time.monotonic(), 30)))
        self.assertFalse(data['runs'][0]['invocations'][0]['executionSuccessful'])

    def test_sarif_uri_roundtrip_and_deleted_side(self):
        value = report(path='dir/a?#% é.py', side='base')
        data = json.loads(render_sarif(value, limits=RecordLimits(), deadline=Deadline(time.monotonic(), 30)))
        result = data['runs'][0]['properties']['baselineHistory'][0]
        location = result['locations'][0]['physicalLocation']['artifactLocation']
        self.assertEqual(unquote(location['uri']), value.findings[0].span.path)
        self.assertNotIn('?', location['uri'])
        self.assertNotIn('#', location['uri'])
        self.assertEqual(result['properties']['side'], 'base')
        self.assertEqual(location['uriBaseId'], '%BASESRCROOT%')

    def test_failure_variant_present_in_sarif_properties(self):
        value = LimitFailure('1', 'limit_failure', {'base_tip': None, 'comparison_base': None, 'head': None,
                              'policy_digest': None, 'reviewer_digest': None}, 2, False, True,
                             'deadline_exceeded', None, ({'domain': 'findings', 'count': None},))
        data = json.loads(render_sarif(value, limits=RecordLimits(), deadline=Deadline(time.monotonic(), 30)))
        run = data['runs'][0]
        self.assertEqual(run['properties']['report']['kind'], 'limit_failure')
        self.assertFalse(run['properties']['report']['analysis_complete'])
        self.assertTrue(run['invocations'][0]['toolExecutionNotifications'])

    def test_cli_render_overflow_returns_schema_valid_failure_all_formats(self):
        value = report('x' * 20000)
        for output_format in ('json', 'markdown', 'sarif'):
            with self.subTest(format=output_format), patch('pullraptor.__main__.review', return_value=(
                    value, Deadline(time.monotonic(), 30), RecordLimits(max_payload_bytes=16384))):
                out = io.StringIO()
                with patch('sys.stdout', out):
                    code = main(['--repo', '.', '--head', 'h', '--format', output_format])
                self.assertEqual(code, 2)
                text = out.getvalue()
                self.assertLessEqual(len(text.encode()), 16384)
                if output_format == 'json':
                    self.assertEqual(json.loads(text)['kind'], 'limit_failure')
                elif output_format == 'sarif':
                    self.assertFalse(json.loads(text)['runs'][0]['invocations'][0]['executionSuccessful'])
                else:
                    self.assertIn('false', text)

    def test_all_full_formats_expose_requested_examined_and_revision_scope(self):
        from pullraptor.models import ScopeEntry, CoverageReceipt
        value = report()
        key = 'file:h:6170702e7079:python_patterns'
        value = replace(value, contract=replace(value.contract, expected_scope=(ScopeEntry(key, 'file', 'h',
                        'python_patterns', path='app.py', path_bytes=b'app.py', reason='changed source'),)),
                        receipts=(CoverageReceipt(key, 'p', 'python_patterns', 'incomplete',
                                  cause='missing_dependency', recovery='Prepare requested repository context'),))
        md = render_markdown(value, limits=RecordLimits(), deadline=Deadline(time.monotonic(), 30))
        self.assertIn('Requested Scope', md)
        self.assertIn('Examined Receipts', md)
        self.assertIn('Base Tip', md)
        self.assertIn('Prepare requested repository context', md)
        sarif = json.loads(render_sarif(value, limits=RecordLimits(), deadline=Deadline(time.monotonic(), 30)))
        raw = sarif['runs'][0]['properties']['report']
        self.assertEqual(raw['contract']['expected_scope'][0]['key'], key)
        self.assertEqual(raw['receipts'][0]['status'], 'incomplete')
        self.assertEqual(raw['contract']['head'], 'h')

    def test_baseline_history_is_not_current_sarif_result(self):
        value = report(side='base')
        data = json.loads(render_sarif(value, limits=RecordLimits(), deadline=Deadline(time.monotonic(), 30)))
        run = data['runs'][0]
        self.assertEqual(run['results'], [])
        self.assertEqual(run['properties']['baselineHistory'][0]['properties']['side'], 'base')
        self.assertEqual(run['properties']['baselineHistory'][0]['locations'][0]['physicalLocation']
                         ['artifactLocation']['uriBaseId'], '%BASESRCROOT%')

    def test_explicit_diff_profile_disclaims_semantic_correctness_security(self):
        value = report()
        value = replace(value, contract=replace(value.contract, profile='diff'), findings=())
        md = render_markdown(value, limits=RecordLimits(), deadline=Deadline(time.monotonic(), 30))
        self.assertIn('Semantic correctness and security were not evaluated', md)
