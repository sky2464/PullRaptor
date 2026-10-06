"""Source-derived locations, strict isolated responses, protocol boundary and binding."""
from collections import namedtuple
from dataclasses import replace
import hashlib
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from pullraptor.models import BlobRef, Deadline, Limits, ProcessResult, Snapshot
from pullraptor.python_facts import bind_facts, extract_python


class ParserContractTests(unittest.TestCase):
    def test_unicode_crlf_coordinates_are_source_derived_exact(self):
        source = '# 🚀\r\ndef café(s=[]):\r\n    s.append("é")\r\n'.encode()
        result = extract_python(source, Limits(), Deadline(time.monotonic(), 30))
        self.assertIsNotNone(result.content)
        pattern = next(item for item in result.content.pattern_facts if item['rule'] == 'PY001')
        self.assertEqual(pattern['coords'], {'start_line': 2, 'end_line': 3, 'start_byte': 8,
                         'end_byte': 44, 'start_column': 1, 'end_column': 18})
        snapshot = Snapshot('head', (BlobRef('app.py', b'app.py', '100644', 'oid', len(source)),))
        bound = bind_facts(result.content, source, snapshot, 'app.py', 'head')
        self.assertEqual(bound.content.pattern_facts[0]['coords'], pattern['coords'])

    def test_wrong_span_and_unknown_path_rejected_when_binding(self):
        source = b'def f(x=[]): x.append(1)\n'
        content = extract_python(source, Limits(), Deadline(time.monotonic(), 30)).content
        self.assertIsNotNone(content)
        snapshot = Snapshot('head', (BlobRef('app.py', b'app.py', '100644', 'oid', len(source)),))
        invalid = dict(content.pattern_facts[0])
        invalid['coords'] = {**invalid['coords'], 'end_byte': 10000}
        with self.assertRaises(ValueError):
            bind_facts(replace(content, pattern_facts=(invalid,)), source, snapshot, 'app.py', 'head')
        with self.assertRaises(ValueError):
            bind_facts(content, source, snapshot, 'missing.py', 'head')

    def test_exact_maximum_source_fits_isolated_base64_protocol(self):
        limits = Limits()
        source = b'#' + b'a' * (limits.max_blob_bytes - 2) + b'\n'
        result = extract_python(source, limits, Deadline(time.monotonic(), 30))
        self.assertIsNotNone(result.content, result.diagnostics)
        self.assertEqual(result.content.blob_digest, hashlib.sha256(source).hexdigest())
        self.assertEqual(len(source), 2097152)

    def test_oversized_source_rejected_before_any_worker_launch(self):
        with patch('pullraptor.python_facts.run_bounded') as launch:
            result = extract_python(b'x' * 101, Limits(max_blob_bytes=100), Deadline(time.monotonic(), 30))
        self.assertIsNone(result.content)
        self.assertEqual(result.diagnostics[0].code, 'LIMIT_EXCEEDED')
        launch.assert_not_called()

    def test_duplicate_response_unknown_fields_and_crash_are_partial(self):
        payloads = (b'{"protocol":"pullraptor_worker_v1","success":true,"success":false}',
                    b'{"protocol":"pullraptor_worker_v1","success":false,"error":{},"publication_authorized":true}')
        responses = [ProcessResult(0, payload, b'', 0.01) for payload in payloads]
        responses += [ProcessResult(-9, b'', b'owned crash fixture', .01),
                      ProcessResult(-9, b'', b'', .01, timed_out=True)]
        for response in responses:
            with self.subTest(response=response), patch('pullraptor.python_facts.run_bounded', return_value=response):
                result = extract_python(b'x=1\n', Limits(), Deadline(time.monotonic(), 30))
            self.assertIsNone(result.content)
            self.assertTrue(result.diagnostics)

    def test_unsupported_minor_runtime_is_not_admitted(self):
        version = namedtuple('Version', 'major minor micro')(3, 13, 0)
        with patch('pullraptor.python_facts.sys.version_info', version):
            result = extract_python(b'x=1\n', Limits(), Deadline(time.monotonic(), 30))
        self.assertIsNone(result.content)
        self.assertTrue(any(item.code == 'RUNTIME_UNSUPPORTED' and item.recovery for item in result.diagnostics))
