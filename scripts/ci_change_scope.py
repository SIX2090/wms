#!/usr/bin/env python3
"""Conservatively classify a verified main push as documentation-only or full CI.

No app imports or writes to Git. Only the explicitly requested output file is
appended. Any uncertainty in event/history/API data requires full validation.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import urllib.request

WORKFLOWS = [('ci.yml', 'WMS CI'), ('verify.yml', 'WMS AI Verification')]
SHA = re.compile(r'[0-9a-fA-F]{40}\Z')


def result(mode='full', reason='unclassified'):
    return {'mode': mode, 'docs_only': mode == 'docs', 'reason': reason}


def allowed_path(path):
    """Exact, case-sensitive allowlist; never normalize an unsafe path into it."""
    if not isinstance(path, str) or any(ord(c) < 32 or ord(c) == 127 for c in path):
        return False
    if '\\' in path or path.startswith('/'):
        return False
    parts = path.split('/')
    if any(part in ('', '.', '..') for part in parts):
        return False
    return path == 'README.md' or (len(parts) >= 3 and parts[0] == 'docs'
                                  and parts[1] in ('ledger', 'audit') and path.endswith('.md'))


def git(*args, cwd=None):
    return subprocess.run(['git', *args], cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, timeout=30).stdout


def read_api(url, token):
    request = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json', 'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'wms-ci-change-scope',
    })
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def baseline_green(repository, base, token, fetch=read_api):
    """Require each exact-base main workflow's newest run/attempt to be green."""
    if not token or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        return False
    if any(part in ('.', '..') for part in repository.split('/')):
        return False
    for filename, name in WORKFLOWS:
        candidates = []
        fetched = 0
        seen_ids = set()
        for page in range(1, 11):
            query = urllib.parse.urlencode({'head_sha': base, 'branch': 'main', 'per_page': 100, 'page': page})
            url = f'https://api.github.com/repos/{repository}/actions/workflows/{filename}/runs?{query}'
            payload = fetch(url, token)
            runs = payload.get('workflow_runs') if isinstance(payload, dict) else None
            total = payload.get('total_count') if isinstance(payload, dict) else None
            if (not isinstance(runs, list) or isinstance(total, bool) or not isinstance(total, int)
                    or total < 0 or len(runs) > 100 or fetched + len(runs) > total):
                return False
            for run in runs:
                if not isinstance(run, dict):
                    return False
                # Any unexpected identity leaves this baseline unverified.
                allowed_paths = {'.github/workflows/' + filename + suffix
                                 for suffix in ('', '@main', '@refs/heads/main')}
                if (run.get('head_sha') != base or run.get('head_branch') != 'main'
                        or run.get('path') not in allowed_paths or run.get('name') != name):
                    return False
                run_id, attempt = run.get('id'), run.get('run_attempt', 1)
                if (isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0
                        or isinstance(attempt, bool) or not isinstance(attempt, int) or attempt <= 0):
                    return False
                if run_id in seen_ids:
                    return False
                seen_ids.add(run_id)
                created = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
                if created.tzinfo is None:
                    return False
                candidates.append((created, run_id, attempt, run))
            fetched += len(runs)
            if fetched >= total:
                break
            if not runs or len(runs) < 100:
                return False
        else:
            return False
        if not candidates:
            return False
        latest = max(candidates, key=lambda item: item[:3])[3]
        if latest.get('status') != 'completed' or latest.get('conclusion') != 'success':
            return False
        # An older run being retried must not lend its historical green result.
        if any(run.get('run_attempt', 1) > 1 and run.get('status') != 'completed'
               for *_, run in candidates):
            return False
    return True


def _classify(event, event_name, repository, token, cwd=None, fetch=read_api):
    if event_name != 'push':
        return result(reason='event_requires_full_validation')
    if not isinstance(event, dict) or event.get('ref') != 'refs/heads/main' or event.get('deleted'):
        return result(reason='not_a_main_push')
    base, head = event.get('before'), event.get('after')
    if (not isinstance(base, str) or not isinstance(head, str) or not SHA.fullmatch(base)
            or not SHA.fullmatch(head) or set(base) == {'0'} or set(head) == {'0'}):
        return result(reason='invalid_commit_sha')
    base, head = base.lower(), head.lower()
    if event.get('forced'):
        return result(reason='forced_push_requires_full_validation')
    event_repo = event.get('repository', {}).get('full_name')
    if not isinstance(event_repo, str) or event_repo.casefold() != repository.casefold():
        return result(reason='repository_mismatch')
    if git('rev-parse', '--verify', 'HEAD', cwd=cwd).strip().decode('ascii') != head:
        return result(reason='checkout_mismatch')
    for commit in (base, head):
        if git('rev-parse', '--verify', commit + '^{commit}', cwd=cwd).strip().decode('ascii') != commit:
            return result(reason='unverified_commit')
    git('merge-base', '--is-ancestor', base, head, cwd=cwd)
    names = git('diff', '--name-only', '--no-renames', '-z', base, head, '--', cwd=cwd)
    if not names:
        return result(reason='empty_diff_requires_full_validation')
    if not names.endswith(b'\0'):
        return result(reason='malformed_diff')
    paths = [name.decode('utf-8', errors='strict') for name in names[:-1].split(b'\0')]
    if not all(allowed_path(path) for path in paths):
        return result(reason='outside_document_allowlist')
    if not baseline_green(repository, base, token, fetch=fetch):
        return result(reason='base_workflows_not_verified_green')
    return result('docs', 'allowlisted_docs_on_verified_green_base')


def classify(event, event_name, repository, token, cwd=None, fetch=read_api):
    try:
        return _classify(event, event_name, repository, token, cwd=cwd, fetch=fetch)
    except Exception:
        return result(reason='scope_check_failed_use_full_validation')


def write_output(path, classification):
    if (classification.get('mode') not in ('docs', 'full')
            or type(classification.get('docs_only')) is not bool
            or classification['docs_only'] != (classification['mode'] == 'docs')):
        raise ValueError('Invalid classification output')
    reason = re.sub(r'[^A-Za-z0-9_.:-]', '_', str(classification['reason']))[:160]
    with Path(path).open('a', encoding='utf-8', newline='\n') as output:
        output.write(f"mode={classification['mode']}\ndocs_only={str(classification['docs_only']).lower()}\nreason={reason}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event-file', default=os.environ.get('GITHUB_EVENT_PATH', ''))
    parser.add_argument('--github-output')
    args = parser.parse_args(argv)
    try:
        event = json.loads(Path(args.event_file).read_text(encoding='utf-8'))
        classification = classify(event, os.environ.get('GITHUB_EVENT_NAME', ''),
                                  os.environ.get('GITHUB_REPOSITORY', ''),
                                  os.environ.get('GITHUB_TOKEN', ''), cwd=Path.cwd())
    except Exception:
        # Do not expose untrusted event/API text, Git output or credentials.
        classification = result(reason='scope_check_failed_use_full_validation')
    print(json.dumps(classification, sort_keys=True))
    if args.github_output:
        try:
            write_output(args.github_output, classification)
        except Exception:
            print('Unable to write GitHub output.', file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
