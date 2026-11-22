# E02-T3 writes construction evidence

Date: 2026-11-22. Mode: development verification of the local publisher transport. Trusted base: `a11d464c0027a8bdfe9b1e8b2df7c1eeff13cdad`. Runtime: Python 3.12.3. This note does not accept E02-A3 or admit a live connector.

Local tests cover a lost POST response reconciled to one owned comment, bounded pagination past the first page, refusal to patch a foreign marker, rate-limit deferral, and three retries on one 30-second deadline. Two owned marker comments that share an obligation key stop before POST or PATCH with `ambiguous_observation_match`. An already expired deadline performs zero attempts.

The same command and raw output are recorded in [../lifecycle/unittest.txt](../lifecycle/unittest.txt). Live GET/POST/PATCH and customer `pullraptor-publish` remain disabled.
