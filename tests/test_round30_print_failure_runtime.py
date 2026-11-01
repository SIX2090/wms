"""Print failures use a synthetic frame and offline result API, no printer."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('scenario',['missing-frame','print-throw','print-throw-offline'])
def test_failed_print_cannot_later_be_confirmed(scenario):
    node=shutil.which('node');assert node
    result=subprocess.run([node,str(ROOT/'tests/js/round30_print_failure.cjs'),str(ROOT),scenario],
        capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
