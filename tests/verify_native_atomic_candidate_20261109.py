"""Verify the merged native implementation, not an obsolete candidate rewrite.

The previous experiment patched an old inline SQLite lock and implemented a
second receipt protocol. It also required both replay/reject for unknown legacy
receipts and both accept/reject for keyless clients. The merged, documented B2
contract retains keyless compatibility and rejects unverifiable legacy content.

Run the complete current transaction, lease, protocol, permission and real
connection modules. Their original assertions run unchanged; fixture setup and
all database access remain behind conftest and the verified kernel boundary.
The complementary all-document receipt fault matrix runs in the unit suite.
"""
from pathlib import Path
import sys


TARGETS = (
    'tests/test_native_request_atomicity.py',
    'tests/test_native_request_lease.py',
    'tests/test_native_merge_protocol_20261109.py',
    'tests/test_native_ai_replay_permissions.py',
    'tests/test_native_request_concurrent.py',
)


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from scripts.verify_db_guard import require_isolated_test_runtime
    profile = require_isolated_test_runtime()
    import pytest

    if not TARGETS or len(set(TARGETS)) != len(TARGETS):
        raise RuntimeError('explicit native regression list is empty or duplicated')
    paths = [root / name for name in TARGETS]
    if not all(path.is_file() and path.parent == root / 'tests' for path in paths):
        raise RuntimeError('explicit native regression module is missing')

    class RequireCompleteRun:
        skipped = False

        def pytest_collection_finish(self, session):
            # These five complete modules contain at least 51 real cases.
            # A collection/import failure or reduced manifest must not pass.
            if len(session.items) < 51:
                raise pytest.UsageError('native regression collection is incomplete')

        def pytest_runtest_logreport(self, report):
            if report.skipped:
                self.skipped = True

        def pytest_sessionfinish(self, session, exitstatus):
            if self.skipped and exitstatus == 0:
                session.exitstatus = 1

    return int(pytest.main(['-q', '--capture=sys', '-p', 'no:cacheprovider',
                           '--log-file', str(profile / 'native-candidate-pytest.log'),
                           *map(str, paths)], plugins=[RequireCompleteRun()]))


if __name__ == '__main__':
    raise SystemExit(main())
