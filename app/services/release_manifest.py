"""Portable release identity. Standard library only; no app import or database access."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

MANIFEST_NAME = 'wms-release.json'
_MUTABLE = {'instance', 'backups', 'logs', 'uploads', '__pycache__', '.git'}
_FIELDS = {'schema_version', 'source_sha', 'ui_sha', 'application_root', 'includes',
           'overlay_roots', 'runtime', 'external_operations_paused', 'files', 'artifact_id'}


def _relative(value):  # no-test:reason=所有路径拒绝条件由test_release_manifest参数化覆盖
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('发布清单含无效相对路径')
    parts = value.split('/')
    if any(part in ('', '.', '..') or part.rstrip(' .') != part for part in parts):
        raise ValueError('发布清单路径不得越界或使用别名')
    return value


def _checked(root, relative):  # no-test:reason=链接及越界拒绝由发布清单端到端测试覆盖
    path = root / _relative(relative)
    for current in (path, *path.parents):
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('发布制品不得使用符号链接或目录联接')
        if current == root:
            break
    return path


def _private(relative):  # no-test:reason=私有数据排除及公开CA证书保留测试覆盖
    parts = relative.lower().split('/')
    name = parts[-1]
    return (bool(set(parts) & _MUTABLE) or name == '.env' or name.startswith('.env.')
            or name.endswith(('.pyc', '.pyo', '.flag', '.key', '.pfx', '.p12', '.keystore'))
            or any(name.endswith(ext) or ext + '-' in name for ext in ('.db', '.sqlite', '.sqlite3')))


def _digest(path):  # no-test:reason=源码/覆盖/解释器篡改和空目录重建测试覆盖
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def _files(root, includes):  # no-test:reason=发布清单增删改及重复范围测试覆盖
    found = {}

    def add(path):  # no-test:reason=通过_files及发布清单测试间接覆盖
        relative = path.relative_to(root).as_posix()
        _checked(root, relative)
        if _private(relative):
            return
        key = relative.casefold()
        if key in found:
            raise ValueError('发布清单含重叠范围或大小写冲突')
        found[key] = {'path': relative, 'size': path.stat().st_size, 'sha256': _digest(path)}

    if not isinstance(includes, list) or not includes:
        raise ValueError('必须明确发布制品文件范围')
    for relative in includes:
        path = _checked(root, relative)
        if _private(relative):
            raise ValueError('私有数据不能作为制品输入范围')
        if path.is_file():
            add(path)
        elif path.is_dir():
            for directory, dirs, names in os.walk(path, followlinks=False):
                current = Path(directory)
                for name in dirs:
                    _checked(root, (current / name).relative_to(root).as_posix())
                dirs[:] = [name for name in dirs
                           if not _private((current / name).relative_to(root).as_posix())]
                for name in names:
                    add(current / name)
        else:
            raise ValueError('发布制品含非普通文件')
    return sorted(found.values(), key=lambda row: row['path'])


def _runtime_summary(report):  # no-test:reason=依赖失败/导入漂移/私有路径脱敏测试覆盖
    if not isinstance(report, dict) or report.get('success') is not True or report.get('failures'):
        raise ValueError('依赖检查未通过，不能封存发布制品')
    version = report.get('python_version', '')
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('缺少实际Python版本')
    packages = []
    for item in report.get('packages', []):
        name, required = item.get('name'), item.get('required')
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9._-]+', name)
                or not isinstance(required, str) or not required
                or item.get('installed') != required or item.get('loaded_version', required) != required):
            raise ValueError('运行依赖版本或实际导入不一致')
        packages.append({'name': name, 'version': required})
    if len({row['name'].casefold() for row in packages}) != len(packages):
        raise ValueError('运行依赖清单重复')
    return {'python_version': version, 'packages': sorted(packages, key=lambda row: row['name'])}


def _identity(manifest):  # no-test:reason=空目录复制身份一致和元数据篡改测试覆盖
    payload = {key: value for key, value in manifest.items() if key != 'artifact_id'}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def build_release_manifest(root, *, source_sha, ui_sha, includes, application_root,
                           overlay_roots, runtime_report, external_operations_paused):
    """Bind immutable files, overlays, runtime versions and the paused-operation policy."""
    root = Path(os.path.abspath(root))
    for sha in (source_sha, ui_sha):
        if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ValueError('发布来源必须使用完整40位Git SHA')
    if type(external_operations_paused) is not bool:
        raise ValueError('暂停状态必须是布尔值')
    if not isinstance(overlay_roots, list):
        raise ValueError('覆盖层范围必须明确列出')
    application = _checked(root, application_root)
    if not application.is_dir():
        raise ValueError('应用目录不存在')
    files = _files(root, includes)
    if not any(row['path'].startswith(application_root + '/') for row in files):
        raise ValueError('应用源码不在发布范围内')
    for relative in overlay_roots:
        _checked(root, relative)
        if not any(row['path'] == relative or row['path'].startswith(relative + '/') for row in files):
            raise ValueError('覆盖文件未纳入发布清单')
    result = {'schema_version': 1, 'source_sha': source_sha, 'ui_sha': ui_sha,
              'application_root': application_root, 'includes': includes,
              'overlay_roots': overlay_roots, 'runtime': _runtime_summary(runtime_report),
              'external_operations_paused': external_operations_paused, 'files': files}
    result['artifact_id'] = _identity(result)
    return result


def verify_release_manifest(root, manifest):
    """Reject changed, missing, injected or unsafe immutable files, without loading WMS."""
    if not isinstance(manifest, dict) or set(manifest) != _FIELDS or manifest['schema_version'] != 1:
        raise ValueError('发布清单格式不支持')
    if manifest['artifact_id'] != _identity(manifest):
        raise ValueError('发布清单内容与规范摘要不一致')
    runtime = manifest['runtime']
    if not isinstance(runtime, dict) or set(runtime) != {'python_version', 'packages'}:
        raise ValueError('发布运行依赖格式错误')
    report = {'success': True, 'python_version': runtime['python_version'], 'failures': [],
              'packages': [{'name': row['name'], 'required': row['version'],
                            'installed': row['version']} for row in runtime['packages']]}
    actual = build_release_manifest(root, source_sha=manifest['source_sha'], ui_sha=manifest['ui_sha'],
        includes=manifest['includes'], application_root=manifest['application_root'],
        overlay_roots=manifest['overlay_roots'], runtime_report=report,
        external_operations_paused=manifest['external_operations_paused'])
    if actual != manifest:
        raise ValueError('发布制品完整性不一致：文件、覆盖、运行依赖或身份已变化')
    return actual
