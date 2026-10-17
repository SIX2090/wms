"""Repair task: AUDIT-FULL-20261016-001-F06; export a fresh, bounded package."""
import argparse
import io
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import zipfile


def _reject_links(path):
    for current in [path, *path.parents]:
        if current.is_symlink():
            raise ValueError('Output/source paths must not contain symbolic links.')
        if current.exists():
            info = current.lstat()
            if getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Output/source paths must not contain junctions or reparse points.')


def _private(name):
    path = PurePosixPath(name)
    parts = [part.casefold() for part in path.parts]
    if any(part in {'instance', 'backups', 'logs', 'uploads', '.git', '__pycache__'} for part in parts):
        return True
    filename = parts[-1]
    return (filename == '.env' or filename.startswith('.env.') or '.bak_' in filename
            or filename.endswith(('.pyc', '.flag', '.pem', '.key', '.pfx', '.p12', '.jks', '.keystore'))
            or any(filename.endswith(ext) or (ext + '-') in filename for ext in ('.db', '.sqlite', '.sqlite3')))


def prepare_sources(root, destination):
    root = Path(os.path.abspath(root))
    destination = Path(os.path.abspath(destination))
    _reject_links(root)
    _reject_links(destination)
    if destination.parent != root / 'dist' or destination.name in {'', '.', '..'}:
        raise ValueError('Output must be a new direct child of the repository dist directory.')
    if destination.exists():
        raise ValueError('Output already exists; choose a new package name. Nothing was removed.')
    top = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], text=True).strip()
    if Path(top).resolve() != root.resolve():
        raise ValueError('RootDir must be the Git repository root.')
    subprocess.run(['git', '-C', str(root), 'diff', '--exit-code', 'HEAD', '--', 'app', 'tools'],
                   check=True, stdout=subprocess.DEVNULL)
    archive = subprocess.check_output(['git', '-C', str(root), 'archive', '--format=zip', 'HEAD', 'app', 'tools'])
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        files = []
        for entry in source.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or path.parts[0] not in {'app', 'tools'}:
                raise ValueError('Unsafe Git archive entry.')
            if entry.is_dir() or _private(entry.filename):
                continue
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError('Tracked symbolic links are not supported in portable packages.')
            files.append(entry)
        if 'app/app.py' not in {entry.filename for entry in files}:
            raise ValueError('Committed app/app.py is missing.')
        # No destructive cleanup, including on failure. mkdir refuses a competing build.
        destination.parent.mkdir(exist_ok=True)
        _reject_links(destination)
        destination.mkdir()
        for entry in files:
            target = destination.joinpath(*PurePosixPath(entry.filename).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:
                output.write(source.read(entry))
    return len(files)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--dist', required=True)
    args = parser.parse_args(argv)
    try:
        count = prepare_sources(args.root, args.dist)
    except (OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print(f'[package] Refused/incomplete: {error}. Existing directories were not removed.', file=sys.stderr)
        return 1
    print(f'[package] Exported {count} committed program files; local data was excluded.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
