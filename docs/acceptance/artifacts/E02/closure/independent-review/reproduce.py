"""Independent, inert E02-A2 authority and zero-write reproduction."""
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import contextlib
import copy
import hashlib
import io
import json
import platform
import sys
from unittest.mock import patch

from pullraptor.publication_contract import PublicationContext, PublicationRange
from pullraptor.publisher import publish_report, main

ROOT = Path(__file__).resolve().parents[6]
FIXTURES = ROOT / 'tests/fixtures/e02'
OUT = Path(__file__).parent
raw = (FIXTURES / 'publisher/trusted-inline-report.json').read_bytes()
original = json.loads(raw)
authority_values = json.loads((FIXTURES / 'publication-binding/trusted-inline-authority.json').read_bytes())
authority_values['permitted_ranges'] = tuple(PublicationRange(**item) for item in authority_values['permitted_ranges'])
authority = PublicationContext(**authority_values)
pr = {'head': {'sha': authority.head}, 'base': {'sha': authority.base_tip}, 'draft': False}
rows = []

def run(name, report=None, report_bytes=None, expected=authority, current=None, preview=False, want=2):
    writes = []
    reads = []
    def api(url, token, method='GET', payload=None):
        reads.append(method)
        if method in ('POST', 'PATCH'):
            writes.append(method)
            return 201, {'id': 9001}
        return (200, []) if 'comments' in url else (200, copy.deepcopy(pr))
    with patch('pullraptor.publisher._github_api_request', side_effect=api), \
         patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')), \
         contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        code = publish_report(original if report is None else report, 'owner/repo', 1, 'inert',
                              expected_context=expected, raw_report_bytes=raw if report_bytes is None else report_bytes,
                              current_authority=(lambda fresh: authority) if current is None else current,
                              preview_only=preview)
    assert code == want, (name, code, want)
    assert writes == (['POST'] if want == 0 and not preview else []), (name, writes)
    rows.append({'scenario': name, 'exit_code': code, 'writes': writes, 'api_methods': reads})

run('exact_literal_report_and_independent_authority', want=0)
run('preview_exact_authority', preview=True, want=0)
run('missing_expected_authority', expected=None)
run('unavailable_current_authority', current=lambda fresh: None)
run('equal_JSON_whitespace_bytes_changed', report_bytes=raw + b' ')
run('dict_does_not_match_original_bytes', report={**original, 'inventory': []})
for field in fields(PublicationContext):
    name = field.name
    value = getattr(authority, name)
    changed = (2 if name == 'pr_number' else () if name == 'permitted_ranges' else
               'sha256' if name == 'object_format' else 'f' * len(value) if name in
               ('head', 'base_tip', 'comparison_base', 'scope_digest', 'report_digest', 'artifact_digest', 'reviewer_digest')
               else value + '-changed')
    run('current_authority_drift:' + name, current=lambda fresh, n=name, v=changed: replace(authority, **{n: v}))
    for target in ('POST', 'PATCH'):
        reads = [0]
        inventories = [0]
        writes = []
        def refresh(fresh, n=name, v=changed):
            reads[0] += 1
            return authority if reads[0] <= 2 else replace(authority, **{n: v})
        def retry_api(url, token, method='GET', payload=None):
            if method in ('POST', 'PATCH'):
                writes.append(method)
                raise RuntimeError('inert failed write')
            if 'comments' in url:
                inventories[0] += 1
                return 200, ([{'id':90, 'body':'<!-- pullraptor:review -->',
                              'user':{'login':'pullraptor-bot'}}] if target == 'PATCH' and inventories[0] == 1 else [])
            return 200, copy.deepcopy(pr)
        with patch('pullraptor.publisher._github_api_request', side_effect=retry_api), \
             patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = publish_report(original, 'owner/repo', 1, 'inert', expected_context=authority,
                                  raw_report_bytes=raw, current_authority=refresh)
        assert code == 2 and writes == [target] and reads[0] == 3, (name, target, code, writes, reads)
        rows.append({'scenario':'retry_drift:' + target + ':' + name, 'exit_code':code,
                     'writes':writes, 'authority_reads':reads[0], 'second_write':'denied'})
for name in ('head', 'base_tip', 'comparison_base'):
    run('abbreviated_identity:' + name, expected=replace(authority, **{name: 'abc'}))
for name in ('artifact_digest', 'reviewer_digest', 'scope_digest', 'report_digest'):
    run('invalid_digest:' + name, expected=replace(authority, **{name: ''}))

def altered(name, edit, want=2):
    report = copy.deepcopy(original)
    edit(report)
    encoded = json.dumps(report).encode()
    # Re-pin byte identity solely to isolate the downstream semantic gate.
    pinned = replace(authority, report_digest=hashlib.sha256(encoded).hexdigest())
    run(name, report, encoded, expected=pinned, current=lambda fresh: pinned, want=want)

for name in ('tool_digest', 'config_digest', 'profile', 'policy_digest'):
    altered('report_contract_tampering:' + name, lambda r, n=name: r['contract'].__setitem__(n, 'changed'))
altered('scope_reason_drift', lambda r: r['contract']['expected_scope'][0].__setitem__('reason', 'changed'))
altered('duplicate_expected_scope', lambda r: r['contract']['expected_scope'].append(copy.deepcopy(r['contract']['expected_scope'][0])))
altered('missing_receipt', lambda r: r.__setitem__('receipts', []))
altered('duplicate_receipt', lambda r: r['receipts'].append(copy.deepcopy(r['receipts'][0])))
for name, value in [('status', 'gap'), ('key', 'foreign'), ('capability', 'other'), ('contract_digest', 'other')]:
    altered('receipt_tampering:' + name, lambda r, n=name, v=value: r['receipts'][0].__setitem__(n, v))
altered('incomplete_discovery', lambda r: r['contract'].__setitem__('discovery_complete', False))
for name, value in [('side', 'base'), ('path', 'deleted.py'), ('start_line', 99), ('end_line', 99)]:
    altered('finding_location:' + name, lambda r, n=name, v=value: r['findings'][0]['span'].__setitem__(n, v), want=3 if name == 'start_line' else 2)
for name, value in [('start_line', True), ('end_line', '1'), ('start_byte', True), ('start_column', '1')]:
    altered('invalid_coordinate_type:' + name, lambda r, n=name, v=value: r['findings'][0]['span'].__setitem__(n, v), want=3)
altered('missing_side', lambda r: r['findings'][0]['span'].__delitem__('side'), want=3)
failure = {'schema':'1', 'kind':'limit_failure', 'known_inputs':{}, 'exit_code':2,
           'analysis_complete':False, 'details_omitted':True, 'cause':'timeout'}
failure_bytes = json.dumps(failure).encode()
pinned = replace(authority, report_digest=hashlib.sha256(failure_bytes).hexdigest())
run('limit_failure', failure, failure_bytes, expected=pinned, current=lambda fresh: pinned)
try:
    authority.head = 'changed'
except FrozenInstanceError:
    rows.append({'scenario':'authority_is_frozen', 'result':'passed'})
else:
    raise AssertionError('mutable authority')
with patch.dict('os.environ', {}, clear=True), patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')), contextlib.redirect_stderr(io.StringIO()):
    assert main([]) == 2
rows.append({'scenario':'beta_publisher_disabled', 'result':'passed'})
source_paths = ['src/pullraptor/' + name + '.py' for name in
                ('publication_contract','publisher','publication_transport','publication_lifecycle','publication_trust','models','evidence','render','beta_admission')]
receipt = {'schema':'pullraptor.e02-independent-reproduction/1',
           'runtime':{'python':sys.version, 'executable':sys.executable, 'platform':platform.platform()},
           'scope':'E02-A2 local publication gate; no live API or reviewed-target execution',
           'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in source_paths},
           'literal_fixture_sha256':{'trusted-inline-report.json':hashlib.sha256(raw).hexdigest(),
                                    'trusted-inline-authority.json':hashlib.sha256((FIXTURES/'publication-binding/trusted-inline-authority.json').read_bytes()).hexdigest()},
           'observations':rows, 'result':'passed', 'final_commit_repin':'pending coordinator integration'}
(OUT/'reproduction.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps({'result':'passed', 'independent_scenarios':len(rows), 'output':str(OUT/'reproduction.json')}))
