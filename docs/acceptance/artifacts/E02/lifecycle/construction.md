# E02-T3 lifecycle construction evidence

Date: 2026-11-22. Mode: implement and development verification of PullRaptor's own tests. Trusted base: `a11d464c0027a8bdfe9b1e8b2df7c1eeff13cdad` (`main` after PR #71). Runtime: Python 3.12.3. This note does not accept E02-A3, enable customer publication, or authorize reviewed-target execution.

The planner now takes `PublicationContext` and a connector-proved owner id. Stable obligation keys include repository, pull request, rule, version, path, obligation, and anchor. Revision observation IDs pin head and witness separately. Duplicate keys stay ambiguous. Findings past the inline cap of 10 stay out of cap and are not marked outdated. An unchanged dismissed witness stays deferred. A changed witness renews the same platform observation id.

Command:

```text
PYTHONPATH=src python3.12 -m unittest tests.test_publication_lifecycle tests.test_publisher tests.test_publisher_fixture_scenarios tests.test_evidence -v
```

Result: 42 tests, OK. Raw output: [unittest.txt](unittest.txt).
