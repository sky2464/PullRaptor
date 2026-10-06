"""Full offline CLI with Python DNS/socket denial and an inherited OS boundary."""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pullraptor.__main__ import main
from tests.helpers import make_repo

REPO_ROOT = Path(__file__).resolve().parents[1]
SOCKET_APIS = ('socket', 'socketpair', 'create_connection', 'getaddrinfo', 'gethostbyname',
               'gethostbyname_ex', 'gethostbyaddr', 'getfqdn')


def denied(*args, **kwargs):
    raise AssertionError('offline network API forbidden')


class TestE01OfflineBoundaries(unittest.TestCase):
    def test_review_cli_does_not_open_sockets(self):
        repo = make_repo({'app.py': b'def f():\n    return 1\n'})
        self.addCleanup(repo.cleanup)
        head = repo.commit({'app.py': b'def f():\n    return 2\n'})
        out = io.StringIO()
        with ExitStack() as stack:
            for name in SOCKET_APIS:
                stack.enter_context(patch(f'socket.{name}', side_effect=denied))
            # Positive controls ensure both classes of interception are active.
            for api, args in ((socket.socket, ()), (socket.getaddrinfo, ('localhost', 1))):
                with self.assertRaisesRegex(AssertionError, 'offline network'):
                    api(*args)
            stack.enter_context(patch('sys.stdout', out))
            code = main(['--repo', str(repo.root), '--base', repo.commit_ids[0], '--head', head,
                         '--exact-base', '--format', 'json', '--no-cache'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())['kind'], 'full')

    def test_subprocess_cli_offline_smoke(self):
        sandbox = shutil.which('sandbox-exec')
        if sys.platform != 'darwin' or not sandbox:
            self.skipTest('macOS inherited process boundary; Linux receipt requires network-none runner')
        repo = make_repo({'mod.py': b'x = 1\n'})
        self.addCleanup(repo.cleanup)
        head = repo.commit({'mod.py': b'x = 2\n'})
        with tempfile.TemporaryDirectory(prefix='e01-offline-home-') as home:
            env = {'PATH': '/opt/homebrew/bin:/usr/bin:/bin', 'HOME': home,
                   'PYTHONPATH': str(REPO_ROOT / 'src'), 'LC_ALL': 'C', 'LANG': 'C'}
            boundary = [sandbox, '-p', '(version 1)(allow default)(deny network*)', sys.executable, '-I', '-S']
            control = subprocess.run(boundary + ['-c',
                'import socket; s=socket.socket(); s.bind(("127.0.0.1",0))'], env=env,
                capture_output=True, text=True, timeout=5)
            self.assertNotEqual(control.returncode, 0)
            self.assertIn('PermissionError', control.stderr)
            # Application APIs are intercepted in this distinct CLI process;
            # OS denial is inherited by isolated parser and Git children.
            driver = '''import sys, socket, ssl
sys.path.insert(0, sys.argv.pop(1))
from pullraptor.__main__ import main
def denied(*args, **kwargs): raise RuntimeError("offline API forbidden")
for name in ("socket", "socketpair", "create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getfqdn"):
    setattr(socket, name, denied)
for function, arguments in ((socket.socket, ()), (socket.getaddrinfo, ("localhost", 1))):
    try: function(*arguments)
    except RuntimeError: pass
    else: raise AssertionError("denial control inactive")
raise SystemExit(main(sys.argv[1:]))
'''
            proc = subprocess.run(boundary + ['-c', driver, str(REPO_ROOT / 'src'), '--repo', str(repo.root),
                '--base', repo.commit_ids[0], '--head', head, '--exact-base', '--format', 'json', '--no-cache'],
                env=env, cwd=home, capture_output=True, text=True, timeout=10)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)['kind'], 'full')
