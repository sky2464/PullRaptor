"""Execute reviewed owned synthetic labels as parser data, with precise pattern claims."""
import hashlib
import json
from pathlib import Path
import time
import unittest
from pullraptor.models import BlobRef, Config, Deadline, Limits, Snapshot
from pullraptor.python_facts import bind_facts, extract_python, resolve_context
from pullraptor.rules import evaluate_rules

CORPUS = Path(__file__).parent / 'fixtures/e01/corpus'


class PinnedCorpusTests(unittest.TestCase):
    def test_each_pinned_rule_case_has_expected_pattern_and_advisory_boundary(self):
        manifest = json.loads((CORPUS / 'manifest.json').read_text())
        payload = (CORPUS / manifest['cases']).read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest['cases_sha256'])
        cases = json.loads(payload)
        for case in cases:
            with self.subTest(case=case['id']):
                source = case['source'].encode()
                self.assertEqual(hashlib.sha256(source).hexdigest(), case['source_sha256'])
                self.assertEqual(case['license'], 'Apache-2.0')
                content = extract_python(source, Limits(), Deadline(time.monotonic(), 30)).content
                self.assertIsNotNone(content)
                snapshot = Snapshot('head', (BlobRef('app.py', b'app.py', '100644', 'source', len(source)),))
                bound = bind_facts(content, source, snapshot, 'app.py', 'head')
                resolved, _ = resolve_context((bound,), snapshot)
                findings = tuple(f for f in evaluate_rules(resolved, snapshot, Config()) if f.rule == case['rule'])
                self.assertEqual(len(findings), case['expected_findings'])
                for finding in findings:
                    self.assertEqual(finding.policy_class, case['expected_policy_class'])
                    self.assertEqual(finding.severity, 'advisory')
                    self.assertEqual(finding.state, 'supported')
                    self.assertEqual(finding.version, '1.0')
                    self.assertTrue(finding.assumptions)
                    self.assertTrue(finding.witness)
                    for word in case['forbidden_claims']:
                        self.assertNotIn(word, finding.claim.lower())
