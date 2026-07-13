from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {'.py', '.html', '.js', '.css', '.md', '.txt', '.bat', '.cmd', '.ps1', '.conf'}
EXCLUDED_PARTS = {
    '.git',
    '.venv',
    'venv',
    'env',
    'runtime',
    'wheelhouse',
    'dist',
    'build',
    '__pycache__',
    'node_modules',
}
EXCLUDED_FILES = {
    Path('app/static/js/xlsx.full.min.js'),
    Path('scripts/verify_wms_bugs.py'),
    Path('scripts/verify_source_encoding.py'),
}

MOJIBAKE_PATTERNS = (
    r'锟斤拷|锛|銆',
    r'娑堟伅|娓叉煋|娴佸紡|杈撳嚭|鍏夋爣',
    r'琛ㄦ牸|婊氬姩|瀹瑰櫒|涓诲唴瀹',
    r'鐢遍噰璐|涓嬫帹鐢熸垚',
    r'璇风‘璁|纭畾缁х画|鍙栨秷|纭',
)


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        relative = path.relative_to(ROOT)
        if relative in EXCLUDED_FILES or any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError as exc:
            failures.append(f'{relative}: UTF-8 解码失败：{exc}')
            continue
        if '\ufffd' in text:
            failures.append(f'{relative}: 包含 Unicode 替换字符 U+FFFD')
        for pattern in MOJIBAKE_PATTERNS:
            match = re.search(pattern, text)
            if not match:
                continue
            line = text.count('\n', 0, match.start()) + 1
            failures.append(f'{relative}:{line}: 命中乱码模式 {match.group(0)!r}')

    if failures:
        print('FAIL SOURCE-ENCODING:')
        for failure in failures:
            print(f'  - {failure}')
        return 1
    print('PASS SOURCE-ENCODING: text sources are valid UTF-8 and contain no known mojibake patterns')
    return 0


if __name__ == '__main__':
    sys.exit(main())
