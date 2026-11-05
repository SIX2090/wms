"""Create/verify the complete artifact receipt; never import WMS or open a database."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from services.release_manifest import MANIFEST_NAME, build_release_manifest, verify_release_manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'verify'])
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--source-sha')
    parser.add_argument('--ui-sha')
    parser.add_argument('--include', action='append', default=[])
    parser.add_argument('--overlay-root', action='append', default=[])
    parser.add_argument('--application-root', default='app')
    parser.add_argument('--runtime-report', type=Path)
    parser.add_argument('--external-operations-paused', action='store_true')
    args = parser.parse_args(argv)
    target = args.root / MANIFEST_NAME
    try:
        if args.action == 'create':
            if target.exists():
                raise ValueError('发布清单已存在，拒绝覆盖')
            if not args.runtime_report:
                raise ValueError('缺少实际运行依赖检查回执')
            manifest = build_release_manifest(args.root, source_sha=args.source_sha,
                ui_sha=args.ui_sha or args.source_sha, includes=args.include,
                application_root=args.application_root, overlay_roots=args.overlay_root,
                runtime_report=json.loads(args.runtime_report.read_text(encoding='utf-8-sig')),
                external_operations_paused=args.external_operations_paused)
            with target.open('x', encoding='utf-8') as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
        else:
            manifest = verify_release_manifest(args.root,
                json.loads(target.read_text(encoding='utf-8-sig')))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'[release] Refused: {error}', file=sys.stderr)
        return 1
    print(json.dumps({'success': True, 'artifact_id': manifest['artifact_id'],
                      'source_sha': manifest['source_sha'], 'files': len(manifest['files'])}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
