"""Static planning consistency checks. Never imports or executes PullRaptor."""
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
QUEUE = ROOT / 'docs/release-tasks.json'
DATA = json.loads(QUEUE.read_text())
BUILD = json.loads((ROOT / 'docs/build-tasks.json').read_text())
BUILD_IDS = {t['id'] for t in BUILD['tasks']}
ACCEPTANCE_IDS = {a for t in BUILD['tasks'] for a in t['acceptance_ids']}

def validate(data):
    tasks = data['tasks']
    ids = [t['id'] for t in tasks]
    assert len(ids) == len(set(ids)), 'duplicate release ID'
    assert set(ids) == {f'BR-{i:02}' for i in range(1, 19)}, 'missing release task'
    by_id = {t['id']: t for t in tasks}
    required = ('title', 'owner_role', 'mode', 'status', 'input_paths', 'output_paths',
                'checks', 'completion', 'operation_gate', 'review_owner', 'allowed_modify_paths')
    for task in tasks:
        assert all(task.get(k) for k in required), ('missing field', task['id'])
        assert task['status'] == 'pending' and task['evidence_status'] == 'not_run', 'unearned status'
        assert set(task['existing_cards']) <= BUILD_IDS, ('unknown build card', task['id'])
        assert set(task['depends_on']) <= set(ids), ('unknown release prerequisite', task['id'])
        assert set(task.get('preparation_requires', [])) <= set(task['depends_on']), 'bad preparation subset'
        assert set(task['output_paths']) <= set(task['allowed_modify_paths']), 'unowned output'
    visited, active = set(), set()
    def visit(cid):
        assert cid not in active, ('dependency cycle', cid)
        if cid in visited:
            return
        active.add(cid)
        for prior in by_id[cid]['depends_on']:
            visit(prior)
        active.remove(cid)
        visited.add(cid)
    for cid in ids:
        visit(cid)
    assert data['ready_for_release_requires'] == [f'BR-{i:02}' for i in range(1, 15)], 'wrong readiness tasks'
    assert data['publication_requires'] == ['BR-15', 'BR-16'], 'missing publication decision'
    assert data['released_verified_requires'] == ['BR-17'], 'missing public verification'
    assert data['conditional_maintenance'] == ['BR-18'], 'invented prior release dependency'
    assert 'BR-10' in by_id['BR-11']['depends_on'], 'docs verification precedes installed bytes'
    assert 'BR-11' in by_id['BR-12']['depends_on'], 'release risk review omits docs/recovery'
    assert 'source-CLI offline review' in ' '.join(by_id['BR-03']['checks']), 'installed check has no artifact'
    assert 'real-repository' in ' '.join(by_id['BR-06']['checks']), 'missing real benchmark assignment'
    assert 'docs/releases/beta-0.1-recovery-rehearsal.json' in by_id['BR-11']['output_paths'], 'late recovery'
    assert 'docs/releases/beta-0.1-recovery-rehearsal.json' in by_id['BR-14']['input_paths'], 'readiness omits recovery'
    conditions = data['conditional_requires']
    caps = [c['capability'] for c in conditions]
    assert len(caps) == len(set(caps)), 'duplicate capability gate'
    assert {'github_ci_publication', 'local_mcp', 'local_secret_patterns', 'usefulness_pilot',
            'target_execution', 'remote_service', 'enterprise'} <= set(caps), 'missing conditional scope'
    for row in conditions:
        assert all(row.get(k) for k in ('trigger', 'acceptance_ids', 'existing_cards', 'evidence_records',
                                      'required_result', 'construction_consumers', 'admission_consumers')), 'incomplete admission gate'
        assert set(row['acceptance_ids']) <= ACCEPTANCE_IDS, 'unknown acceptance criterion'
        assert set(row['existing_cards']) <= BUILD_IDS, 'unknown gate owner'
        assert row['construction_consumers'] == ['BR-08'], 'unconsumed construction inventory'
        assert row['admission_consumers'] == ['BR-14'], 'acceptance consumed before artifact producer'
    assert 'conditional_requires' in data['readiness_rule'], 'fixed task list bypasses optional gates'
    cap_path = 'docs/releases/beta-0.1-capability-gates.json'
    assert cap_path in by_id['BR-01']['output_paths'], 'capability mapping has no producer'
    assert all(cap_path in by_id[c]['input_paths'] for c in ('BR-08', 'BR-14')), 'unconsumed mapping'
    return {'release_tasks': len(tasks), 'referenced_build_cards': len({c for t in tasks for c in t['existing_cards']}),
            'conditional_admission_rows': len(conditions), 'acyclic': True}

result = validate(DATA)
controls = {
    'missing_owner': lambda d: d['tasks'][0].pop('owner_role'),
    'duplicate_release_id': lambda d: d['tasks'].append(copy.deepcopy(d['tasks'][0])),
    'self_dependency': lambda d: d['tasks'][0]['depends_on'].append('BR-01'),
    'unknown_build_card': lambda d: d['tasks'][0]['existing_cards'].append('E99-T1'),
    'unearned_acceptance': lambda d: d['tasks'][0].update(status='passed'),
    'missing_optional_gate': lambda d: d.update(conditional_requires=[c for c in d['conditional_requires'] if c['capability'] != 'local_mcp']),
    'missing_docs_artifact_dependency': lambda d: d['tasks'][10]['depends_on'].remove('BR-10'),
    'missing_recovery_input': lambda d: d['tasks'][13]['input_paths'].remove('docs/releases/beta-0.1-recovery-rehearsal.json'),
    'unowned_output': lambda d: d['tasks'][0]['allowed_modify_paths'].clear(),
    'admission_before_artifact_producer': lambda d: d['conditional_requires'][2].update(admission_consumers=['BR-08']),
}
rejected = []
for name, mutate in controls.items():
    damaged = copy.deepcopy(DATA)
    mutate(damaged)
    try:
        validate(damaged)
    except (AssertionError, KeyError):
        rejected.append(name)
    else:
        raise AssertionError(('negative control accepted', name))
plan = (ROOT / DATA['plan']).read_text()
for task in DATA['tasks']:
    assert f"### {task['id']}: {task['title']}" in plan, 'Markdown/JSON task drift'
    assert all(check in plan for check in task['checks']), ('Markdown/JSON step drift', task['id'])
    assert all(f'`{p}`' in plan for p in task['output_paths']), ('Markdown/JSON file drift', task['id'])
paths = ['Master-Plan.md', 'docs/build-task-board.md', 'docs/worker-dispatch.md', DATA['plan'],
         'docs/reviews/2026-10-05-beta-release-readiness.md']
links = 0
for name in paths:
    path = ROOT / name
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
        target = target.strip('<>')
        if '://' in target or target.startswith('#'):
            continue
        assert (path.parent / target.split('#', 1)[0]).resolve().exists(), ('broken link', name, target)
        links += 1
    assert not re.search(r'^- \[[xX]\]', path.read_text(), re.MULTILINE), ('unearned checkbox', name)
master = (ROOT / 'Master-Plan.md').read_text()
for package in range(1, 12):
    assert f'| E{package:02} |' in master, 'roadmap package lost'
assert DATA['inspected_source_revision'] in master, 'source revision absent'
result.update(negative_controls_rejected=rejected, local_links_checked=links,
              markdown_json_task_parity=True, runtime_tests='not_run', builds='not_run',
              scope='static documentation structure and references only; not product acceptance')
print(json.dumps(result, indent=2))
