"""Check the selected interpreter before release, without importing WMS or opening a DB."""
from __future__ import annotations

import argparse
import importlib
from importlib import metadata
import json
from pathlib import Path
import re
import sys


def read_pins(path):
    """Only the production manifest's explicit version pins are accepted."""
    pins = {}
    for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)', line)
        if not match:
            raise ValueError(f'Requirements line {number} is not an exact version pin.')
        name = re.sub(r'[-_.]+', '-', match[1]).lower()
        if name in pins:
            raise ValueError(f'Duplicate requirement: {name}.')
        pins[name] = match[2]
    if not pins:
        raise ValueError('The dependency manifest is empty.')
    return pins


def check_runtime_dependencies(requirements):
    """Compare installed distributions and the actual security-critical imports."""
    result = {'success': False, 'python': sys.executable, 'python_version': sys.version.split()[0],
              'requirements': str(Path(requirements).resolve()), 'packages': [], 'failures': []}
    try:
        pins = read_pins(requirements)
    except (OSError, UnicodeError, ValueError) as error:
        result['failures'].append(str(error))
        return result
    for name, required in pins.items():
        row = {'name': name, 'required': required, 'installed': None}
        result['packages'].append(row)
        try:
            row['installed'] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result['failures'].append(f'{name}: missing; required {required}.')
            continue
        if row['installed'] != required:
            result['failures'].append(f'{name}: installed {row["installed"]}; required {required}.')
        # Distribution metadata alone misses a PYTHONPATH shadow or stale import.
        if name in {'pypdf', 'certifi'}:
            try:
                module = importlib.import_module(name)
                row['loaded_version'] = str(getattr(module, '__version__', 'unknown'))
                row['module_file'] = str(Path(module.__file__).resolve())
                if row['loaded_version'] != required:
                    result['failures'].append(f'{name}: imported {row["loaded_version"]}; required {required}.')
            except Exception as error:
                result['failures'].append(f'{name}: cannot import ({type(error).__name__}).')
    result['success'] = not result['failures']
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requirements', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'app/requirements.txt')
    parser.add_argument('--json', action='store_true', help='Print versions/paths only; no environment secrets.')
    args = parser.parse_args(argv)
    report = check_runtime_dependencies(args.requirements)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report['success']:
        print(f'PASS: {len(report["packages"])} pinned dependencies and actual PDF/TLS imports match.')
    else:
        for failure in report['failures']:
            print('[ERROR] ' + failure, file=sys.stderr)
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
