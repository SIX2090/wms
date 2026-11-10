"""JUnit failure diagnostics retain the real test result and escape annotations."""
from pathlib import Path
import runpy
import subprocess
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runner():
    return runpy.run_path(str(ROOT / 'scripts/run_tests_sharded.py'))


def test_report_failures_preserves_case_and_assertion(tmp_path, capsys, runner):
    report = tmp_path / 'unit.xml'
    report.write_text('<testsuites><testsuite><testcase classname="tests.orders" name="test_replay">'
                      '<failure>assert 2 == 1\n100%\n::warning::untrusted</failure></testcase>'
                      '<testcase name="control"/></testsuite></testsuites>', encoding='utf-8')
    assert not runner['report_failures'](report)
    output = capsys.readouterr().out
    assert 'tests.orders::test_replay%0Aassert 2 == 1' in output
    assert '100%25%0A::warning::untrusted' in output
    assert '\n::warning::' not in output
    summary = report.with_suffix('.md').read_text(encoding='utf-8')
    assert '1 / 2 cases' in summary and 'assert 2 == 1' in summary


def test_first_annotation_lists_every_failure(tmp_path, capsys, runner):
    """GitHub keeps 10 error annotations per step; the first one must carry all names."""
    cases = ''.join(f'<testcase classname="tests.m{i}" name="test_{i}"><failure>boom {i}</failure></testcase>'
                    for i in range(12))
    report = tmp_path / 'unit.xml'
    report.write_text(f'<testsuite>{cases}<testcase name="ok"/></testsuite>', encoding='utf-8')
    assert not runner['report_failures'](report)
    errors = [line for line in capsys.readouterr().out.splitlines() if line.startswith('::error')]
    assert len(errors) == 13
    assert errors[0].startswith('::error title=Unit failures 12/13::')
    assert all(f'tests.m{i}::test_{i}' in errors[0] for i in range(12))
    assert all(e.startswith('::error title=Unit test failure::') for e in errors[1:])


@pytest.mark.parametrize('content', [None, '', '<invalid', '<testsuites/>'])
def test_missing_malformed_or_empty_report_is_not_success(tmp_path, runner, content):
    report = tmp_path / 'unit.xml'
    if content is not None:
        report.write_text(content)
    assert not runner['report_failures'](report)


@pytest.mark.parametrize('exit_code,write_report,failure,expected', [
    (0, True, False, 0), (1, True, False, 1), (5, False, False, 5),
    (0, False, False, 1), (0, True, True, 1),
])
def test_main_preserves_exit_and_rejects_stale_report(tmp_path, runner, exit_code, write_report, failure, expected):
    from scripts import linux_test_runtime
    report = tmp_path / 'output/unit-shard-0.xml'
    report.parent.mkdir()
    report.write_text('<testsuite><testcase name="stale"/></testsuite>')
    report.with_suffix('.md').write_text('old success')
    def execute(command, **kwargs):
        assert command[-2:] == ['--junitxml', str(report)]
        assert 'tests/test_synthetic.py' in command
        assert not report.exists()
        assert not report.with_suffix('.md').exists()
        if write_report:
            error = '<failure>assert 2 == 1</failure>' if failure else ''
            report.write_text('<testsuite><testcase name="current">' + error + '</testcase></testsuite>')
        return exit_code
    with mock.patch.object(linux_test_runtime, 'require_subprocess_boundary'), \
            mock.patch.dict(runner['main'].__globals__, {'REPO_ROOT': tmp_path, 'collect': lambda *_: ['tests/test_synthetic.py']}), \
            mock.patch.dict('os.environ', {}, clear=True), mock.patch('sys.argv', ['synthetic']), \
            mock.patch.object(subprocess, 'call', execute):
        assert runner['main']() == expected
