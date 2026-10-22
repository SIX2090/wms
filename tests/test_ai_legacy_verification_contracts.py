"""Run the legacy verifiers against isolated fixtures and exercise their rejection paths."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('script', ['verify_ai_photo_document_flow.py', 'verify_ai_stage3_agents.py', 'verify_ai_material_category_coding.py'])
def test_legacy_verification_scripts(script, tmp_path):
    env = dict(os.environ, FLASK_ENV='testing', DATABASE_URL='sqlite:///:memory:',
               WMS_DATABASE_URI='sqlite:///' + (tmp_path / 'isolated.db').as_posix(),
               WMS_ALLOW_INSECURE_COOKIE='1', WMS_SKIP_STARTUP_DB_UPGRADE='1',
               PYTHONUTF8='1', PYTHONIOENCODING='utf-8', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts' / script)], cwd=ROOT,
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=50)
    assert result.returncode == 0, result.stdout + result.stderr


def test_replenishment_verifier_rejects_mislabeled_threshold(tmp_path):
    program = '''
import runpy,sys
sys.path.insert(0,'app')
import ai.agents.replenishment as module
original=module._generate_replenishment_explanation
module._generate_replenishment_explanation=lambda item: original(item).replace('最低库存：','安全库存：')
checks=runpy.run_path('scripts/verify_ai_stage3_agents.py')
assert checks['test_replenishment']() is False, 'verifier accepted a mislabeled threshold'
'''
    env = dict(os.environ, FLASK_ENV='testing', DATABASE_URL='sqlite:///:memory:',
               WMS_DATABASE_URI='sqlite:///' + (tmp_path / 'isolated.db').as_posix(),
               PYTHONUTF8='1', PYTHONIOENCODING='utf-8', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    result = subprocess.run([sys.executable, '-c', program], cwd=ROOT, env=env,
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
