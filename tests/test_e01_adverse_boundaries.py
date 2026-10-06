"""Concrete adverse fixtures for source, Git, worker and process authority."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from pullraptor.git_snapshot import read_blob, read_snapshot, resolve_inputs
from pullraptor.models import Deadline, Limits, ProcessBounds, ProcessResult
from pullraptor.process import run_bounded
from pullraptor.python_facts import extract_python
from pullraptor.parser_worker import extractor_identity
from tests.helpers import make_repo


class AdverseBoundaries(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo({'a.py': b'x=1\n'})
    def tearDown(self):
        self.repo.cleanup()
    def deadline(self):
        return Deadline(time.monotonic(), 30)
    def git(self, *args, input=None):
        return subprocess.check_output(('git', *args), cwd=self.repo.root, input=input)

    def test_refs_moving_after_resolution_do_not_change_snapshot(self):
        base, comparison, head = resolve_inputs(self.repo.root, 'main', 'main', Limits(), self.deadline())
        moved = self.repo.commit({'a.py': b'x=999\n'})
        self.assertNotEqual(head, moved)
        snapshot = read_snapshot(self.repo.root, head, Limits(), self.deadline())
        blob = next(b for b in snapshot.blobs if b.path == 'a.py')
        self.assertEqual(read_blob(self.repo.root, blob.blob_oid, Limits(), self.deadline()), b'x=1\n')
        self.assertEqual((base, comparison, head), (self.repo.commit_ids[0],) * 3)

    def test_spaces_tabs_newlines_paths_are_exact(self):
        names = ('space path.py', 'tab\tpath.py', 'line\npath.py')
        head = self.repo.commit({name: b'x=2\n' for name in names})
        snapshot = read_snapshot(self.repo.root, head, Limits(), self.deadline())
        found = {b.path_bytes: b.path for b in snapshot.blobs}
        for name in names:
            self.assertEqual(found[name.encode()], name)

    def test_real_submodule_and_symlink_modes_not_followed(self):
        (self.repo.root / 'link.py').symlink_to('/does-not-exist-raptor-boundary')
        self.git('add', '--', 'link.py')
        self.git('update-index', '--add', '--cacheinfo', '160000,' + self.repo.commit_ids[0] + ',nested.py')
        self.git('commit', '-m', 'inert mode fixture')
        head = self.git('rev-parse', 'HEAD').decode().strip()
        snapshot = read_snapshot(self.repo.root, head, Limits(), self.deadline())
        modes = {b.path: b.mode for b in snapshot.blobs}
        self.assertEqual(modes['link.py'], '120000')
        self.assertEqual(modes['nested.py'], '160000')
        self.assertFalse((self.repo.root / 'nested.py').exists())

    def test_multiple_merge_bases_require_explicit_comparison(self):
        root = self.repo.commit_ids[0]
        tree = self.git('rev-parse', root + '^{tree}').decode().strip()
        a = self.git('commit-tree', tree, '-p', root, input=b'a\n').decode().strip()
        b = self.git('commit-tree', tree, '-p', root, input=b'b\n').decode().strip()
        left = self.git('commit-tree', tree, '-p', a, '-p', b, input=b'left\n').decode().strip()
        right = self.git('commit-tree', tree, '-p', b, '-p', a, input=b'right\n').decode().strip()
        with self.assertRaisesRegex(ValueError, 'Multiple merge bases'):
            resolve_inputs(self.repo.root, left, right, Limits(), self.deadline())
        self.assertEqual(resolve_inputs(self.repo.root, left, right, Limits(), self.deadline(), exact_base=True), (left, left, right))

    def test_non_utf8_path_is_visible_not_discarded(self):
        path = os.fsencode(self.repo.root) + b'/bad-\xff.py'
        with open(path, 'wb') as stream:
            stream.write(b'x=1\n')
        self.git('add', '-A')
        self.git('commit', '-m', 'undecodable inert path')
        head = self.git('rev-parse', 'HEAD').decode().strip()
        snapshot = read_snapshot(self.repo.root, head, Limits(), self.deadline())
        self.assertTrue(any(b.path is None and b.path_bytes == b'bad-\xff.py' for b in snapshot.blobs))
        self.assertTrue(any(d.code == 'PATH_NON_UTF8' for d in snapshot.diagnostics))

    def test_missing_revision_refuses_without_remote_helper(self):
        sentinel = self.repo.root / 'executed'
        self.git('config', 'remote.origin.url', 'ext::touch ' + str(sentinel))
        self.git('config', 'remote.origin.promisor', 'true')
        self.git('config', 'extensions.partialClone', 'origin')
        with self.assertRaises(ValueError):
            resolve_inputs(self.repo.root, 'f' * 40, 'main', Limits(), self.deadline())
        self.assertFalse(sentinel.exists())

    def test_process_does_not_inherit_open_handle(self):
        read, write = os.pipe()
        os.set_inheritable(write, True)
        program = f"import os\ntry: os.fstat({write}); print('inherited')\nexcept OSError: print('closed')"
        try:
            result = run_bounded((sys.executable, '-I', '-S', '-c', program), cwd=self.repo.root, env={}, deadline=self.deadline(), bounds=ProcessBounds())
            self.assertEqual(result.stdout.strip(), b'closed')
            self.assertEqual(result.returncode, 0)
        finally:
            os.close(read)
            os.close(write)

    def test_exact_maximum_source_fits_isolated_protocol(self):
        source = b'#' + b'x' * (Limits().max_blob_bytes - 2) + b'\n'
        self.assertEqual(len(source), 2097152)
        parsed = extract_python(source, Limits(), self.deadline())
        self.assertIsNotNone(parsed.content)
        self.assertEqual(parsed.content.blob_digest, hashlib.sha256(source).hexdigest())

    def test_worker_crash_and_duplicate_record_are_partial(self):
        for result in (ProcessResult(7, b'', b'crash', 0), ProcessResult(0, b'{"protocol":"pullraptor_worker_v1","success":false,"success":true}', b'', 0)):
            with self.subTest(result=result), patch('pullraptor.python_facts.run_bounded', return_value=result):
                parsed = extract_python(b'x=1\n', Limits(), self.deadline())
                self.assertIsNone(parsed.content)
                self.assertEqual(parsed.diagnostics[0].code, 'PY_PARSE_FAILED')

    def test_isolated_worker_request_duplicate_rejected(self):
        worker = Path(__file__).resolve().parents[1] / 'src/pullraptor/parser_worker.py'
        with tempfile.TemporaryDirectory() as neutral:
            result = subprocess.run((sys.executable, '-I', '-S', str(worker)), cwd=neutral, env={}, input=b'{"protocol":"pullraptor_worker_v1","protocol":"pullraptor_worker_v1","source_base64":"eD0xCg=="}', capture_output=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')

    def test_all_extractor_components_affect_identity(self):
        original = Path.read_bytes
        baseline = extractor_identity()
        for name in ('parser_worker.py', 'python_facts.py', 'models.py'):
            with self.subTest(name=name):
                def changed(path):
                    return original(path) + (b'\n# mutation\n' if path.name == name else b'')
                with patch.object(Path, 'read_bytes', changed):
                    self.assertNotEqual(extractor_identity(), baseline)
