"""Bind Windows release reuse to committed inputs, complete assets and real validation.

Standard library and existing release-manifest helpers only. Never imports WMS
or accesses a database. GitHub I/O is limited to the existing Actions gh session.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_portable_sources import _private
from check_portable_runtime import RECEIPT_CHECKS as CHECKS
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from services.release_manifest import _identity, verify_release_manifest

SHA = re.compile(r'[0-9a-f]{40}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')
PYTHON_VERSION = '3.11.9'


def release_names(version):
    if not isinstance(version, str) or not re.fullmatch(r'20\d{2}\.\d{2}\.\d+', version):
        raise ValueError('Invalid calendar release version.')
    stem = f'WMS-{version}-windows-x64'
    return dict(tag=f'windows-v{version}', archive=stem+'.zip', checksum=stem+'.zip.sha256',
                proof=stem+'.release.json', runtime=stem+'.runtime.json')


def build_inputs(root, ref='HEAD'):
    if ref != 'HEAD' and not SHA.fullmatch(ref):
        raise ValueError('Build input ref must be HEAD or a complete commit SHA.')
    output = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-rz', '--full-tree', ref,
                                      'app', 'tools', '.github/workflows/windows-release.yml'])
    rows = []
    for record in output.split(b'\0'):
        if not record:
            continue
        header, raw = record.split(b'\t', 1)
        mode, kind, sha = header.decode('ascii').split()
        name = raw.decode('utf-8')
        if _private(name):
            continue
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('Build inputs must be regular committed files.')
        rows.append(dict(path=name, mode=mode, blob=sha))
    if not {'app/app.py', 'app/requirements.txt', 'tools/build_portable_dist.ps1',
            '.github/workflows/windows-release.yml'} <= {r['path'] for r in rows}:
        raise ValueError('Build input scope is incomplete.')
    payload = dict(schema_version=1, python_version=PYTHON_VERSION, runner='windows-2022',
                   bootstrap_pins=['pip==26.1.1', 'setuptools==82.0.1', 'wheel==0.47.0'],
                   files=sorted(rows, key=lambda row: row['path']))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def select_release(version, source_sha, fingerprint, existing=None, proof=None):
    names = release_names(version)
    if (not isinstance(source_sha, str) or not SHA.fullmatch(source_sha) or
            not isinstance(fingerprint, str) or not DIGEST.fullmatch(fingerprint)):
        raise ValueError('Missing exact source/build identity.')
    plan = dict(schema_version=1, version=version, source_sha=source_sha,
                input_fingerprint=fingerprint, names=names, state='build')
    if existing is None:
        return plan
    if not isinstance(existing, dict) or existing.get('draft') is not False or existing.get('tag_name') != names['tag']:
        raise ValueError('Existing release is not a complete published candidate.')
    if not isinstance(proof, dict) or proof.get('schema_version') != 1:
        raise ValueError('Existing tag has no validated binding proof; choose a new version.')
    if proof.get('version') != version or proof.get('input_fingerprint') != fingerprint:
        raise ValueError('Version tag conflicts with current committed build inputs.')
    if not SHA.fullmatch(str(proof.get('source_sha', ''))) or not DIGEST.fullmatch(str(proof.get('archive_sha256', ''))):
        raise ValueError('Existing proof identity is invalid.')
    plan.update(state='reuse_pending_verification', reused_source_sha=proof['source_sha'])
    return plan


def file_digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def verify_archive(path, proof):
    prefix = 'WMS-'+proof['version']+'/'
    with zipfile.ZipFile(path) as archive:
        entries = {}
        for item in archive.infolist():
            name = item.filename
            if item.is_dir():
                continue
            relative = PurePosixPath(name)
            if (not name.startswith(prefix) or '\\' in name or ':' in name or
                    relative.is_absolute() or '..' in relative.parts or
                    name.casefold() in entries or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('Unsafe or duplicate archive member.')
            entries[name.casefold()] = item
        manifest = json.loads(archive.read(prefix+'wms-release.json').decode('utf-8-sig'))
        if (manifest.get('artifact_id') != _identity(manifest) or
                manifest.get('artifact_id') != proof.get('artifact_id') or
                manifest.get('source_sha') != proof['source_sha'] or
                manifest.get('ui_sha') != proof['source_sha'] or
                manifest.get('runtime', {}).get('python_version') != PYTHON_VERSION):
            raise ValueError('Archive identity/runtime does not match its release proof.')
        declared = set()
        for row in manifest['files']:
            name = row['path']
            if name.startswith('/') or '\\' in name or ':' in name or any(x in ('', '.', '..') for x in name.split('/')):
                raise ValueError('Unsafe manifest path.')
            member = prefix+name
            if member.casefold() in declared or member.casefold() not in entries:
                raise ValueError('Manifest file is missing or duplicated.')
            declared.add(member.casefold())
            item = entries[member.casefold()]
            if type(row['size']) is not int or row['size'] != item.file_size:
                raise ValueError('Archive file size changed.')
            digest = hashlib.sha256()
            with archive.open(item) as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != row['sha256']:
                raise ValueError('Archive file content changed.')
        for key, item in entries.items():
            relative = item.filename[len(prefix):]
            if key in declared or relative == 'wms-release.json':
                continue
            if relative.endswith(('.pyc', '.pyo')) and '__pycache__' in relative.split('/'):
                continue
            raise ValueError('Archive contains an undeclared file.')


def verify_downloads(release, directory, plan, tag_sha, *, allow_draft=False):
    names = plan['names'];directory = Path(directory)
    if (not isinstance(release, dict) or release.get('tag_name') != names['tag'] or
            release.get('draft') is not allow_draft):
        raise ValueError('Unexpected release publication state.')
    assets = release.get('assets')
    if not isinstance(assets, list) or any(not isinstance(x, dict) for x in assets):
        raise ValueError('Malformed release assets.')
    if len({x.get('name') for x in assets}) != len(assets):
        raise ValueError('Duplicate release asset names.')
    for key in ('archive', 'checksum', 'proof', 'runtime'):
        name = names[key];asset = next((x for x in assets if x.get('name') == name), None);path = directory/name
        if (not asset or asset.get('state') != 'uploaded' or not path.is_file() or
                type(asset.get('size')) is not int or asset['size'] <= 0 or path.stat().st_size != asset['size'] or
                asset.get('digest') != 'sha256:'+file_digest(path)):
            raise ValueError('Missing, incomplete or corrupt release asset: '+name)
    proof = json.loads((directory/names['proof']).read_text(encoding='utf-8-sig'))
    runtime = json.loads((directory/names['runtime']).read_text(encoding='utf-8-sig'))
    if (proof.get('schema_version') != 1 or proof.get('version') != plan['version'] or
            proof.get('source_sha') != tag_sha or proof.get('input_fingerprint') != plan['input_fingerprint'] or
            proof.get('archive_name') != names['archive'] or
            proof.get('archive_sha256') != file_digest(directory/names['archive']) or
            proof.get('runtime_receipt_sha256') != file_digest(directory/names['runtime'])):
        raise ValueError('Release tag, source, inputs and assets do not agree.')
    if (runtime.get('success') is not True or runtime.get('source_sha') != tag_sha or
            runtime.get('artifact_id') != proof.get('artifact_id') or runtime.get('checks') != CHECKS):
        raise ValueError('Actual isolated runtime validation receipt is missing.')
    checksum = (directory/names['checksum']).read_text(encoding='ascii').strip()
    if checksum != proof['archive_sha256']+'  '+names['archive']:
        raise ValueError('Checksum sidecar does not match the exact archive.')
    verify_archive(directory/names['archive'], proof)
    return proof


def _gh(*args, missing=False):
    result = subprocess.run(['gh', *args], capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        if missing and '(HTTP 404)' in result.stderr:
            return None
        raise ValueError('GitHub operation failed; no release may be claimed as verified.')
    return result.stdout


def _json_api(endpoint, missing=False):
    value = _gh('api', endpoint, missing=missing)
    return None if value is None else json.loads(value)


def tag_commit(repository, tag):
    value = _json_api(f'repos/{repository}/git/ref/tags/{tag}', missing=True)
    if value is None:
        return None
    value = value['object']
    for _ in range(6):
        if not SHA.fullmatch(str(value.get('sha', ''))):
            break
        if value.get('type') == 'commit':
            return value['sha']
        if value.get('type') != 'tag':
            break
        value = _json_api(f'repos/{repository}/git/tags/{value["sha"]}')['object']
    raise ValueError('Release tag does not resolve to a complete commit.')


def target_eligibility(root, repository, source_sha, event_name='workflow_dispatch'):
    """Discard a proved stale automatic target; never relax a packaging gate."""
    if (not isinstance(source_sha, str) or not SHA.fullmatch(source_sha)
            or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)):
        raise ValueError('Missing exact release target or repository.')
    remote = _json_api(f'repos/{repository}/git/ref/heads/main')['object']['sha']
    if not isinstance(remote, str) or not SHA.fullmatch(remote):
        raise ValueError('Current main was not verified as a complete commit SHA.')
    result = dict(state='eligible', source_sha=source_sha, current_main=remote)
    if source_sha == remote:
        return result
    if event_name != 'workflow_run':
        raise ValueError('Only current accepted main may be packaged.')
    # main may have advanced after checkout. Fetch only its exact checked SHA;
    # a missing object/fetch error or failed ancestry check is never a skip.
    subprocess.run(['git', '-C', str(root), 'fetch', '--no-tags', 'origin', remote],
                   check=True, capture_output=True, text=True)
    relation = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', source_sha, remote],
                              capture_output=True, text=True)
    if relation.returncode != 0:
        raise ValueError('Automatic target is not a verified ancestor of current main.')
    result['state'] = 'stale_skipped'
    return result


def _actions_outputs(result, path):
    values = {key: result[key] for key in ('state', 'source_sha', 'current_main', 'version', 'work_dir') if key in result}
    values.update(result.get('names', {}))
    with Path(path).open('a', encoding='utf-8') as stream:
        for key, value in values.items():
            if '\n' in str(value) or '\r' in str(value):
                raise ValueError('Unsafe Actions output.')
            stream.write(key + '=' + str(value) + '\n')


def _record_stale(result):
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if path:
        with Path(path).open('a', encoding='utf-8') as stream:
            stream.write('Windows release: stale_skipped; target: ' + result['source_sha']
                         + '; current main: ' + result['current_main']
                         + '; no stale package published.' + '\n')
            if result.get('unpublished_draft'):
                stream.write('Unpublished draft retained for review: ' + result['unpublished_draft'] + '\n')


def plan_release(root, version, work, repository, event_name='workflow_dispatch'):
    root = Path(root);work = Path(work)
    source = subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'], text=True).strip()
    eligibility = target_eligibility(root, repository, source, event_name)
    if eligibility['state'] == 'stale_skipped':
        return eligibility
    work.mkdir(parents=True, exist_ok=False)
    fingerprint = build_inputs(root);names = release_names(version)
    existing = _json_api(f'repos/{repository}/releases/tags/{names["tag"]}', missing=True)
    tagged = tag_commit(repository, names['tag'])
    if existing is None and tagged is not None:
        raise ValueError('Version tag already exists without a complete release.')
    proof = None
    if existing is not None:
        _gh('release','download',names['tag'],'--repo',repository,'--dir',str(work),
            *[arg for key in ('archive','checksum','proof','runtime') for arg in ('--pattern',names[key])])
        proof = json.loads((work/names['proof']).read_text(encoding='utf-8-sig'))
    plan = select_release(version, source, fingerprint, existing, proof)
    plan.update(repository=repository, root=str(root.resolve()), work_dir=str(work.resolve()))
    if existing is not None:
        if build_inputs(root, proof['source_sha']) != fingerprint:
            raise ValueError('Reused source commit does not have identical actual build inputs.')
        subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',proof['source_sha'],source],check=True)
        verify_downloads(existing,work,plan,tagged)
        plan['state'] = 'reused_verified'
    eligibility = target_eligibility(root, repository, source, event_name)
    if eligibility['state'] == 'stale_skipped':
        plan.update(eligibility)
    (work/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    return plan


def seal_release(plan, package, archive):
    package = Path(package);archive = Path(archive);work = Path(plan['work_dir']);names=plan['names']
    if plan['state'] != 'build' or archive.name != names['archive'] or archive.parent.resolve() != work.resolve():
        raise ValueError('Unexpected build output.')
    manifest = verify_release_manifest(package,json.loads((package/'wms-release.json').read_text(encoding='utf-8-sig')))
    runtime_path = work/names['runtime'];runtime=json.loads(runtime_path.read_text(encoding='utf-8-sig'))
    if (manifest['source_sha'] != plan['source_sha'] or manifest['ui_sha'] != plan['source_sha'] or
            manifest['runtime']['python_version'] != PYTHON_VERSION or runtime.get('success') is not True or
            runtime.get('checks') != CHECKS or runtime.get('source_sha') != plan['source_sha'] or
            runtime.get('artifact_id') != manifest['artifact_id']):
        raise ValueError('Current build has no matching actual runtime validation.')
    proof=dict(schema_version=1,version=plan['version'],source_sha=plan['source_sha'],
               input_fingerprint=plan['input_fingerprint'],archive_name=names['archive'],
               archive_sha256=file_digest(archive),artifact_id=manifest['artifact_id'],
               runtime_receipt_sha256=file_digest(runtime_path))
    verify_archive(archive,proof)
    with (work/names['checksum']).open('x',encoding='ascii') as stream:
        stream.write(proof['archive_sha256']+'  '+names['archive']+'\n')
    with (work/names['proof']).open('x',encoding='utf-8') as stream:
        json.dump(proof,stream,indent=2)
    return proof


def publish_release(plan, notes, event_name='workflow_dispatch'):
    if plan['state'] != 'build':
        raise ValueError('Only newly built candidates may publish.')
    repository=plan['repository'];names=plan['names'];work=Path(plan['work_dir'])
    eligibility = target_eligibility(plan['root'], repository, plan['source_sha'], event_name)
    if eligibility['state'] == 'stale_skipped':
        return eligibility
    if build_inputs(plan['root']) != plan['input_fingerprint']:
        raise ValueError('Committed build inputs changed.')
    _gh('release','create',names['tag'],*[str(work/names[k]) for k in ('archive','checksum','proof','runtime')],
        '--repo',repository,'--target',plan['source_sha'],'--title','WMS Windows '+plan['version'],
        '--notes-file',str(notes),'--draft','--prerelease')
    # The by-tag endpoint only promises published releases. Authenticated listing
    # also exposes our just-created draft; never mistake a missing draft for GO.
    drafts = _json_api(f'repos/{repository}/releases?per_page=100')
    matches = [row for row in drafts if row.get('tag_name') == names['tag']]
    if len(matches) != 1:
        raise ValueError('The uploaded draft release could not be identified.')
    release = matches[0]
    if release.get('target_commitish') != plan['source_sha']:
        raise ValueError('Draft release targets a different source commit.')
    existing_tag = tag_commit(repository,names['tag'])
    if existing_tag is not None and existing_tag != plan['source_sha']:
        raise ValueError('Version tag changed during build; preserve the existing release.')
    verify_downloads(release,work,plan,plan['source_sha'],allow_draft=True)
    eligibility = target_eligibility(plan['root'], repository, plan['source_sha'], event_name)
    if eligibility['state'] == 'stale_skipped':
        eligibility['unpublished_draft'] = names['tag']
        return eligibility
    _gh('release','edit',names['tag'],'--repo',repository,'--draft=false')
    published=_json_api(f'repos/{repository}/releases/tags/{names["tag"]}')
    verify_downloads(published,work,plan,tag_commit(repository,names['tag']))
    return dict(state='built_verified',source_sha=plan['source_sha'],tag=names['tag'],url=published['html_url'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('target');p.add_argument('--root',type=Path,required=True);p.add_argument('--target-sha',required=True);p.add_argument('--github-output',type=Path,required=True)
    p=sub.add_parser('plan');p.add_argument('--root',type=Path,required=True);p.add_argument('--version',required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--github-output',type=Path,required=True)
    for action in ('seal','publish'):
        p=sub.add_parser(action);p.add_argument('--plan',type=Path,required=True)
        if action=='seal':p.add_argument('--package',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
        else:p.add_argument('--notes',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        event_name = os.environ.get('GITHUB_EVENT_NAME', 'workflow_dispatch')
        if args.action in ('target', 'plan'):
            repository=os.environ.get('GITHUB_REPOSITORY','')
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('Missing Actions repository.')
            if args.action == 'target':
                result = target_eligibility(args.root, repository, args.target_sha, event_name)
            else:
                result=plan_release(args.root,args.version,args.work,repository,event_name)
            _actions_outputs(result, args.github_output)
        else:
            plan=json.loads(args.plan.read_text(encoding='utf-8'))
            result=seal_release(plan,args.package,args.archive) if args.action=='seal' else publish_release(plan,args.notes,event_name)
            if args.action == 'publish' and result.get('state') == 'stale_skipped':
                # Prevent a discarded plan from later being treated as a built
                # verified release or retried as a current candidate.
                plan.update(result)
                args.plan.write_text(json.dumps(plan, indent=2), encoding='utf-8')
        if result.get('state') == 'stale_skipped':
            _record_stale(result)
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError,zipfile.BadZipFile) as error:
        print('[windows-release] Refused: '+str(error),file=sys.stderr);return 1
    print(json.dumps(result,ensure_ascii=True));return 0


if __name__=='__main__':
    raise SystemExit(main())
