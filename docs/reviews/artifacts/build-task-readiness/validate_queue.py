import ast
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[4]
DATA=json.loads((ROOT/'docs/build-tasks.json').read_text())
COUNTS={2:4,3:3,4:3,5:4,6:4,7:3,8:4,9:3,10:4,11:3}

def validate(data, check_inputs=False):
    tasks=data['tasks']
    ids=[c['id'] for c in tasks]
    assert len(ids)==len(set(ids)), 'duplicate task ID'
    byid={c['id']:c for c in tasks}
    required=('id','package','plan','plan_task','title','owner_role','observed_state','scope','input_paths','output_paths','interface_summary','build_prerequisites','acceptance_ids','activation_gates','test_names','validation_commands','adverse_cases','next_action','depends_on','prerequisite_inputs','operation_prerequisites','construction_status','review_owner')
    for c in tasks:
        assert all(key in c and (c[key] or key in ('depends_on','build_prerequisites','prerequisite_inputs','operation_prerequisites','test_names')) for key in required), ('missing field',c['id'])
        assert all(x in byid and x!=c['id'] for x in c['depends_on']), ('bad dependency',c['id'])
        assert c['construction_status']==('ready' if not c['depends_on'] else 'waiting_for_task_outputs'), ('dishonest readiness',c['id'])
        assert c['evidence_status']=='not_run', ('unearned evidence',c['id'])
        assert c['code_revision']==data['code_revision']==c['trusted_base_revision'], ('revision mismatch',c['id'])
        assert (ROOT/c['plan']).is_file(), ('missing plan',c['id'],c['plan'])
        for p in c['prerequisite_inputs']:
            assert p['producer_ids'] and all(x in byid for x in p['producer_ids']), ('unknown producer',c['id'])
            assert all(any(p['path']==o or p['path'].startswith(o.rstrip('/')+'/') or o.startswith(p['path'].rstrip('/')+'/') for o in byid[x]['output_paths']) for x in p['producer_ids']), ('output ownership mismatch',c['id'],p)
            assert set(p['producer_ids'])<=set(c['depends_on']), ('missing input producer dependency',c['id'])
        for p in c['operation_prerequisites']:
            assert all(x in byid and x!=c['id'] for x in p['task_ids']), ('unknown operation dependency',c['id'])
        if check_inputs:
            for p in c['input_paths']:
                result=subprocess.run(['git','cat-file','-e',data['code_revision']+':'+p.split(':',1)[0]],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                assert result.returncode==0, ('missing pinned input',c['id'],p)
    # Every main child task is owned by at least one T card, not merely a design card.
    for package,count in COUNTS.items():
        for n in range(1,count+1):
            assert any(c['package']==f'E{package:02d}' and c['id'].startswith(f'E{package:02d}-T{n}') for c in tasks), ('unowned plan task',package,n)
    assert any(c['id'].startswith('E01-T9') for c in tasks), 'missing E01 Task 9'
    expected={'E01-A1','E01-A2','E01-A3'} | {f'E{p:02d}-A{n}' for p,count in COUNTS.items() for n in range(1,count+1)}
    actual={a for c in tasks for a in c['acceptance_ids']}
    assert actual==expected, ('acceptance coverage',expected-actual,actual-expected)
    visited=set(); active=set()
    def visit(cid):
        assert cid not in active, ('dependency cycle',cid)
        if cid in visited:return
        active.add(cid)
        for predecessor in byid[cid]['depends_on']:visit(predecessor)
        active.remove(cid);visited.add(cid)
    for cid in byid:visit(cid)
    capabilities={cid for row in data['capability_ownership'] for cid in row['ids']}
    assert capabilities=={f'F{n:02d}' for n in range(1,33)}, 'capability coverage'
    deferred={cid for row in data['capability_ownership'] if row.get('state')=='deferred' for cid in row['ids']}
    assert deferred=={'F26','F27','F29','F30'}, 'deferred scope drift'
    return {'cards':len(tasks),'main_plan_tasks':1+sum(COUNTS.values()),'acceptance_ids':len(expected),'capability_ids':len(capabilities),'construction_ready':sum(not c['depends_on'] for c in tasks),'acyclic':True}

result=validate(DATA,check_inputs=True)
negative=[]
def two_node_cycle(d):
    first,second=d['tasks'][:2]
    first['depends_on'].append(second['id'])
    second['depends_on'].append(first['id'])
    first['construction_status']=second['construction_status']='waiting_for_task_outputs'
mutations={
    'missing_owner':lambda d:d['tasks'][0].pop('owner_role'),
    'duplicate_id':lambda d:d['tasks'].append(copy.deepcopy(d['tasks'][0])),
    'unknown_dependency':lambda d:d['tasks'][0]['depends_on'].append('E99-T1'),
    'unearned_readiness':lambda d:d['tasks'][0].update(construction_status='accepted'),
    'self_cycle':lambda d:d['tasks'][0]['depends_on'].append(d['tasks'][0]['id']),
    'two_node_cycle':two_node_cycle,
    'missing_child_task':lambda d:d.update(tasks=[c for c in d['tasks'] if c['id']!='E11-T3']),
    'missing_acceptance_id':lambda d:[c.update(acceptance_ids=[a for a in c['acceptance_ids'] if a!='E02-A4']) for c in d['tasks']],
}
for name,mutate in mutations.items():
    damaged=copy.deepcopy(DATA);mutate(damaged)
    try:validate(damaged)
    except (AssertionError,KeyError):negative.append(name)
    else:raise AssertionError(('negative control accepted',name))

# Check all local Markdown links in the edited handoff documents, never execute candidate code.
handoffs={'Master-Plan.md','docs/planning-contract.md','docs/worker-dispatch.md','docs/build-task-board.md','docs/build-interfaces.md','docs/reviews/2026-10-03-build-task-readiness.md','docs/superpowers/specs/2026-10-03-e05-security-models.md'} | {c['plan'] for c in DATA['tasks']}
paths=[ROOT/p for p in sorted(handoffs)]
links=0
for path in paths:
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',path.read_text()):
        target=target.strip('<>')
        if '://' in target or target.startswith('#'):continue
        destination=(path.parent/target.split('#',1)[0]).resolve()
        assert destination.exists(), ('broken local link',str(path.relative_to(ROOT)),target)
        links+=1
declarations=0
for path in (ROOT/'tests').glob('test*.py'):
    tree=ast.parse(path.read_text())
    declarations+=sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_') for n in ast.walk(tree))
result.update(negative_controls_rejected=negative,local_links_checked=links,static_test_declarations=declarations,product_runtime='not_run',validator='stdlib-only static documentation checker; no project imports')
print(json.dumps(result,indent=2))
