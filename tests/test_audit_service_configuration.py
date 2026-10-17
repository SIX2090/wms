"""Repair task: AUDIT-FULL-20261016-001-F07A; isolated launchers/fake services only."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import service_launcher as launcher
import service_control


@pytest.mark.parametrize('mode,extra,secure,insecure', [
    ('https', {}, 'true', None), ('https', {'SESSION_COOKIE_SECURE':'yes'}, 'yes', None),
    ('trusted-http', {}, None, '1'), ('', {'SESSION_COOKIE_SECURE':'1'}, '1', None),
    ('', {'WMS_ALLOW_INSECURE_COOKIE':'true'}, None, 'true')])
def test_build_service_env(mode, extra, secure, insecure):
    base = {'WMS_DEPLOYMENT_MODE':mode, 'WMS_ALLOW_AUTO_SECRET_KEY':'0', 'SYNTHETIC_OTHER_SETTING':'keep', **extra}
    before = dict(base)
    env = launcher.build_service_env(base)
    assert env.get('SESSION_COOKIE_SECURE') == secure
    assert env.get('WMS_ALLOW_INSECURE_COOKIE') == insecure
    assert env['WMS_SKIP_AUTO_UPDATE'] == '1' and env['WMS_NO_DB_TOUCH'] == '1'
    assert env['WMS_ALLOW_AUTO_SECRET_KEY'] == '0' and env['SYNTHETIC_OTHER_SETTING'] == 'keep'
    assert base == before


@pytest.mark.parametrize('base', [{}, {'WMS_DEPLOYMENT_MODE':'unknown'},
    {'WMS_DEPLOYMENT_MODE':'https','SESSION_COOKIE_SECURE':'0'},
    {'WMS_DEPLOYMENT_MODE':'trusted-http','WMS_ALLOW_INSECURE_COOKIE':'0'},
    {'WMS_DEPLOYMENT_MODE':'trusted-http','SESSION_COOKIE_SECURE':'true'},
    {'WMS_DEPLOYMENT_MODE':'https','WMS_PORT':'0'}])
def test_build_service_env_rejects_ambiguous_or_contradictory_configuration(base):
    with pytest.raises(ValueError):
        launcher.build_service_env(base)


def clean_env(directory, **values):
    env = dict(os.environ)
    for key in ['WMS_DEPLOYMENT_MODE','SESSION_COOKIE_SECURE','WMS_ALLOW_INSECURE_COOKIE','WMS_PORT']:
        env.pop(key, None)
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', DATABASE_URL='sqlite:///' + str(directory / 'not-created.db'), **values)
    return env


@pytest.mark.parametrize('mode', ['https', 'trusted-http'])
def test_main_config_only_does_not_create_database_or_import_application(tmp_path, mode):
    result = subprocess.run([sys.executable, str(ROOT/'app/service_launcher.py'), '--check'],
                            env=clean_env(tmp_path, WMS_DEPLOYMENT_MODE=mode), capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    assert not (tmp_path/'not-created.db').exists()
    assert b'Flask config loaded' not in result.stdout


def test_main_missing_database_does_not_start_or_initialize(tmp_path, monkeypatch):
    monkeypatch.setenv('WMS_DEPLOYMENT_MODE', 'https')
    monkeypatch.delenv('SESSION_COOKIE_SECURE', raising=False)
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///' + str(tmp_path/'absent.db'))
    start = MagicMock()
    monkeypatch.setattr(launcher.subprocess, 'call', start)
    assert launcher.main([]) == 2
    start.assert_not_called()
    assert not (tmp_path/'absent.db').exists()


def test_main_invalid_existing_database_is_preserved(tmp_path, monkeypatch):
    database = tmp_path/'invalid.db'
    database.write_bytes(b'synthetic invalid database must be retained')
    monkeypatch.setenv('WMS_DEPLOYMENT_MODE','https')
    monkeypatch.delenv('SESSION_COOKIE_SECURE',raising=False)
    monkeypatch.setenv('DATABASE_URL','sqlite:///' + str(database))
    start=MagicMock()
    monkeypatch.setattr(launcher.subprocess,'call',start)
    assert launcher.main([])==2
    start.assert_not_called()
    assert database.read_bytes()==b'synthetic invalid database must be retained'


@pytest.mark.parametrize('kind', ['correct', 'foreign', 'changed'])
def test_check_service_health(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(launcher, 'APP_DIR', tmp_path)
    row={'pid':12,'executable':r'C:\Python\python.exe','command':f'"C:\\Python\\python.exe" "{tmp_path / "run_server.py"}"','ticks':'123'}
    if kind == 'foreign': row['command'] = row['command'].replace('run_server.py','other.py')
    second = dict(row, ticks='999') if kind == 'changed' else row
    snapshots = [{'listeners':[12],'processes':[row]}, {'listeners':[12],'processes':[second]}]
    calls=[]
    def snapshot(port):
        calls.append(port)
        return snapshots[min(len(calls)-1, 1)] if kind != 'changed' or len(calls)<3 else {'listeners':[],'processes':[]}
    monkeypatch.setattr(service_control, 'process_snapshot', snapshot)
    response = MagicMock();response.__enter__.return_value.status=200
    http = MagicMock(return_value=response)
    monkeypatch.setattr(launcher.urllib.request, 'urlopen', http)
    monkeypatch.setattr(launcher.time, 'sleep', lambda delay: None)
    if kind == 'correct': assert launcher.check_service_health({'WMS_PORT':'8080'}) == 0
    else:
        with pytest.raises(ValueError): launcher.check_service_health({'WMS_PORT':'8080'})
    if kind == 'foreign': http.assert_not_called()


def service_layout(tmp_path):
    assert tmp_path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    app=tmp_path/'app'; scripts=tmp_path/'scripts';app.mkdir();scripts.mkdir()
    for name in ['service_launcher.py','config.py','runtime_guard.py']:
        shutil.copyfile(ROOT/'app'/name, app/name)
    shutil.copyfile(ROOT/'scripts/restore_backup.py',scripts/'restore_backup.py')
    (app/'instance').mkdir()
    # Core schema only, no account records or real business data.
    from tests.test_audit_install_preservation import validator
    with sqlite3.connect(app/'instance/inventory.db') as connection:
        for name, fields in validator.REQUIRED_SCHEMA.items():
            columns=','.join('"'+field+'" TEXT' for field in sorted(fields))
            connection.execute(f'CREATE TABLE "{name}" ({columns})')
    (app/'run_server.py').write_text("import os,json,sys\nfrom pathlib import Path\nimport config\nconfig.validate_production_security_config()\nPath(__file__).with_name('child.json').write_text(json.dumps({k:os.environ.get(k) for k in ['SESSION_COOKIE_SECURE','WMS_ALLOW_INSECURE_COOKIE','WMS_SKIP_AUTO_UPDATE']}))\nsys.exit(7)\n",encoding='utf-8')
    return app


@pytest.mark.skipif(os.name != 'nt', reason='Windows actual auto-start batch with synthetic child')
@pytest.mark.parametrize('mode', ['https','trusted-http'])
def test_auto_entry_applies_mode_and_propagates_child_failure(tmp_path, mode):
    app=service_layout(tmp_path)
    shutil.copyfile(ROOT/'app/start_wms_auto.bat',app/'start_wms_auto.bat')
    env=clean_env(tmp_path,WMS_DEPLOYMENT_MODE=mode)
    env['DATABASE_URL']='sqlite:///' + str(app/'instance/inventory.db')
    env['PATH']=str(Path(sys.executable).parent)+os.pathsep+env['PATH']
    result=subprocess.run(['cmd','/d','/c',str(app/'start_wms_auto.bat')],env=env,capture_output=True,timeout=45)
    assert result.returncode == 7, result.stderr.decode(errors='replace')
    data=json.loads((app/'child.json').read_text())
    assert data['WMS_SKIP_AUTO_UPDATE']=='1'
    assert data['SESSION_COOKIE_SECURE']=='true' if mode=='https' else data['WMS_ALLOW_INSECURE_COOKIE']=='1'


@pytest.mark.parametrize('mode,expected', [('https','https|true|unset|8080'),('trusted-http','trusted-http|unset|1|8080')])
def test_batch_preflight_outputs_only_validated_configuration_without_starting(tmp_path,mode,expected):
    app=service_layout(tmp_path)
    env=clean_env(tmp_path,WMS_DEPLOYMENT_MODE=mode)
    env['DATABASE_URL']='sqlite:///' + str(app/'instance/inventory.db')
    env['SECRET_KEY']='synthetic-test-only-do-not-emit'
    result=subprocess.run([sys.executable,str(app/'service_launcher.py'),'--batch-config'],env=env,capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    assert result.stdout.decode().strip()==expected
    assert not (app/'child.json').exists()


def test_auto_entry_retains_direct_run_server_contract():
    source=(ROOT/'app/start_wms_auto.bat').read_text(encoding='utf-8')
    assert '"%PYTHON_CMD%" "%~dp0run_server.py"' in source
    assert '--batch-config' in source
    assert source.index('--batch-config')<source.index('"%PYTHON_CMD%" "%~dp0run_server.py"')
    assert 'WMS_SKIP_AUTO_UPDATE=1' in source


@pytest.mark.skipif(os.name != 'nt', reason='Windows fresh installer config fragment, fake app only')
@pytest.mark.parametrize('name',['install.bat','install_e_wms.bat'])
@pytest.mark.parametrize('choice',['default','https','deny'])
def test_fresh_installer_configuration_passes_gate_without_overriding_optout(tmp_path,name,choice):
    from tests.test_audit_install_preservation import layout, run_fragment, stage, source
    target, package, profile=layout(tmp_path)
    (target/'instance/inventory.db').unlink()  # Generated file inside the verified temporary sandbox.
    shutil.copyfile(ROOT/'app/config.py',target/'config.py')
    (target/'app.py').write_text("import config\nfrom pathlib import Path\nconfig.validate_production_security_config()\nclass Context:\n def push(self):pass\n def pop(self):pass\nclass App:\n def app_context(self):return Context()\napp=App()\ndef initialize_database():Path(__file__).with_name('fake-init.marker').write_text('called')\n",encoding='utf-8')
    env={'SESSION_COOKIE_SECURE':'true' if choice=='https' else '', 'WMS_ALLOW_INSECURE_COOKIE':'0' if choice=='deny' else '', 'FLASK_ENV':'production'}
    result=run_fragment(tmp_path,name,target,package,profile,stage(source(name),6,7)+'\nexit /b 0',env)
    assert (result.returncode==0)==(choice!='deny')
    assert (target/'fake-init.marker').exists()==(choice!='deny')


@pytest.fixture(scope='module')
def fake_nssm(tmp_path_factory):
    if os.name!='nt': pytest.skip('Windows fake service executable')
    directory=tmp_path_factory.mktemp('fake-service-only')
    assert directory.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    executable=directory/'fake-nssm.exe'
    code='''using System; using System.IO;
public class FakeService { public static int Main(string[] args) {
 File.AppendAllText(Environment.GetEnvironmentVariable("FIXTURE_SERVICE_LOG"), String.Join("|",args)+"\\n");
 if(args.Length>0 && args[0]=="query") return Int32.Parse(Environment.GetEnvironmentVariable("FIXTURE_SERVICE_QUERY_RC") ?? "5");
 if(args.Length>0 && args[0]=="-NoProfile") return Int32.Parse(Environment.GetEnvironmentVariable("FIXTURE_PORT_RC") ?? "2");
 if(args.Length>0 && args[0]=="status") return Environment.GetEnvironmentVariable("FIXTURE_EXISTS")=="1" ? 0 : 1;
 string key=args.Length>2 ? args[0]+" "+args[2] : String.Join(" ",args);
 return key==Environment.GetEnvironmentVariable("FIXTURE_FAIL") ? 7 : 0;
}}'''
    env=dict(os.environ,FIXTURE_COMPILE_OUTPUT=str(executable),FIXTURE_COMPILE_CODE=code)
    compiled=subprocess.run(['powershell','-NoProfile','-Command','Add-Type -TypeDefinition $env:FIXTURE_COMPILE_CODE -OutputAssembly $env:FIXTURE_COMPILE_OUTPUT -OutputType ConsoleApplication'],env=env,capture_output=True,timeout=40)
    assert compiled.returncode==0,compiled.stderr.decode(errors='replace')
    return executable


@pytest.mark.parametrize('failure',['existing','set AppEnvironmentExtra','set AppDirectory','none'])
def test_cloud_registration_never_stops_existing_service_and_propagates_failure(tmp_path,fake_nssm,failure):
    source=(ROOT/'deploy_cloud.bat').read_text(encoding='utf-8')
    # Both old/new versions have the status query. Bound the actual registration fragment;
    # every service command runs the generated marker-only executable, never NSSM/SC.
    start=source.index('"%NSSM_EXE%" status %SERVICE_NAME% >nul 2>&1')
    end=source.index('REM ── 手机 App',start)
    body=source[start:end]+'\nexit /b 0\n:service_setup_failed\nexit /b 1\n'
    script=tmp_path/'register-test.cmd'
    script.write_bytes(('@echo off\n'+body).replace('\n','\r\n').encode())
    log=tmp_path/'fake-service.log'
    env=dict(os.environ,NSSM_EXE=str(fake_nssm),SERVICE_NAME='WMS',INSTALL_DIR=str(tmp_path),WMS_DEPLOYMENT_MODE='https',
             FIXTURE_SERVICE_LOG=str(log),FIXTURE_EXISTS='1' if failure=='existing' else '',FIXTURE_FAIL=failure)
    result=subprocess.run(['cmd','/d','/c',str(script)],env=env,capture_output=True,timeout=30)
    assert (result.returncode==0)==(failure=='none')
    calls=log.read_text().splitlines()
    assert not any(line.startswith(('stop|','remove|')) for line in calls)
    if failure=='existing': assert calls==['status|WMS']
    if failure=='none':
        assert any('AppEnvironmentExtra|WMS_DEPLOYMENT_MODE=https|WMS_SKIP_AUTO_UPDATE=1' in line for line in calls)


def test_cloud_preflight_precedes_mutation_and_health_is_strict():
    source=(ROOT/'deploy_cloud.bat').read_text(encoding='utf-8')
    assert 'sc.exe query' in source and source.index('sc.exe query') < source.index('git fetch')
    assert source.index('--check-idle --check-database') < source.index('"%NSSM_EXE%" install')
    assert 'service_launcher.py" --health\nif errorlevel 1 goto :service_setup_failed' in source
    assert 'AppExit 2 Exit' in source


def test_cloud_reuses_nested_runtime_without_downloading(tmp_path, fake_nssm):
    directory=tmp_path/'runtime/nssm'
    nested=directory/'nssm-2.24/win64'
    nested.mkdir(parents=True)
    shutil.copyfile(fake_nssm,nested/'nssm.exe')
    # If the old entry attempts network/extraction, both commands execute this
    # marker-only stub. No network, archive extraction or real service is possible.
    shutil.copyfile(fake_nssm,tmp_path/'powershell.exe')
    source=(ROOT/'deploy_cloud.bat').read_text(encoding='utf-8')
    start=source.index('set "NSSM_EXE=')
    end=source.index('"%NSSM_EXE%" status %SERVICE_NAME% >nul 2>&1',start)
    script=tmp_path/'runtime-test.cmd'
    script.write_bytes(('@echo off\nsetlocal EnableDelayedExpansion\n'+source[start:end]+'\nexit /b 0\n').replace('\n','\r\n').encode())
    log=tmp_path/'fake-service.log'
    env=dict(os.environ,INSTALL_DIR=str(tmp_path),NSSM_DIR=str(directory),NSSM_URL='https://example.invalid/not-downloaded',
             FIXTURE_SERVICE_LOG=str(log),FIXTURE_FAIL='',FIXTURE_EXISTS='',FIXTURE_PORT_RC='0',PATH=str(tmp_path)+os.pathsep+os.environ['PATH'])
    result=subprocess.run(['cmd','/d','/c',str(script)],env=env,capture_output=True,input=b'\n',timeout=30)
    assert result.returncode==0
    assert not log.exists(), 'Existing runtime must not trigger download/extraction'


@pytest.mark.parametrize('query_rc,port_rc,allowed', [(0,0,False),(5,0,False),(1060,1,False),(1060,2,False),(1060,0,True)])
def test_cloud_initial_preflight_checks_absence_before_any_mutation(tmp_path,fake_nssm,query_rc,port_rc,allowed):
    source=(ROOT/'deploy_cloud.bat').read_text(encoding='utf-8')
    marker='REM Repair task: AUDIT-FULL-20261016-001-F07A.'
    assert marker in source, 'Existing service and port must be checked before deployment begins'
    body=source[source.index(marker):source.index('REM ---- Step 1: Git check ----')]
    for name in ['sc.exe','powershell.exe']:
        shutil.copyfile(fake_nssm,tmp_path/name)
    script=tmp_path/'initial-test.cmd'
    script.write_bytes(('@echo off\nsetlocal EnableDelayedExpansion\n'+body+'\nexit /b 0\n').replace('\n','\r\n').encode())
    log=tmp_path/'fake-service.log'
    marker_file=tmp_path/'existing-business.txt';marker_file.write_bytes(b'keep')
    env=dict(os.environ,SERVICE_NAME='WMS',WMS_DEPLOYMENT_MODE='https',FIXTURE_SERVICE_LOG=str(log),
             FIXTURE_SERVICE_QUERY_RC=str(query_rc),FIXTURE_PORT_RC=str(port_rc),PATH=str(tmp_path)+os.pathsep+os.environ['PATH'])
    result=subprocess.run(['cmd','/d','/c',str(script)],env=env,capture_output=True,timeout=20)
    assert (result.returncode==0)==allowed
    assert marker_file.read_bytes()==b'keep'
    assert not any(line.startswith(('stop|','remove|','install|')) for line in log.read_text().splitlines())
