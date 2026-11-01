from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.support import evidence_dir
"""Three new photo pagehide simulations and selected unchanged local regressions."""
from pathlib import Path
import hashlib,json,os,re,shutil,sqlite3,subprocess
import pytest

SOURCE=Path(__file__).resolve().parents[1]
ROOT=SOURCE.parent
NEW=['leave-during-read','leave-during-request','leave-before-success-callback']
OLD=['scanner-no-device','scanner-busy','scanner-sync-throw','scanner-init-throw','scanner-disconnect',
     'scanner-duplicate','scanner-cancel-before-open','scanner-late-callback','scanner-pagehide',
     'scanner-track-stop-failure','photo-timeout','photo-network','photo-business-error','photo-superseded']

class GuardConnection(sqlite3.Connection):
    def execute(self,sql,*args,**kwargs):
        assert not re.search(r'\bREPLACE\b',sql,re.I),'REPLACE forbidden'
        return super().execute(sql,*args,**kwargs)

@pytest.fixture
def fresh_guard(tmp_path):
    path=tmp_path/'fresh-qa45-guard.sqlite'
    assert not path.exists()
    assert path.resolve().is_relative_to(tmp_path.resolve())
    with sqlite3.connect(path,factory=GuardConnection) as connection:
        denied={sqlite3.SQLITE_DELETE,sqlite3.SQLITE_DROP_TABLE,sqlite3.SQLITE_DROP_INDEX,
            sqlite3.SQLITE_DROP_VIEW,sqlite3.SQLITE_DROP_TRIGGER,sqlite3.SQLITE_ALTER_TABLE}
        connection.set_authorizer(lambda action,*args:sqlite3.SQLITE_DENY if action in denied else sqlite3.SQLITE_OK)
        connection.execute('CREATE TABLE qa45_guard (marker TEXT NOT NULL)')
        connection.execute('INSERT INTO qa45_guard VALUES (?)',('QA45_NO_BUSINESS',))
        connection.commit()
    connection.close()
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    yield
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    # Fresh guard DB persists. No WMS actor, login, schema cleanup, unlink or restore.

def run_node(script,scenario,evidence=None):
    command=[shutil.which('node'),'--max-old-space-size=96','--require',str(SOURCE/'tests/audit_regressions/network_guard.cjs'),
             str(SOURCE/'tests/audit_regressions'/script),str(SOURCE),scenario]
    if evidence:command.append(str(evidence))
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr

@pytest.mark.parametrize('scenario',NEW)
def test_photo_pagehide_new_contract(fresh_guard,scenario):
    run_node('js/round45_photo_exit.cjs',scenario,evidence_dir()/(scenario+'.json'))

@pytest.mark.parametrize('scenario',OLD)
def test_existing_device_failure_assertions_unchanged(fresh_guard,scenario):
    run_node('js/round30_device_failure.cjs',scenario)
