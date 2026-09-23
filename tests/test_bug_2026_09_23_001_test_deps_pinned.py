# -*- coding: utf-8 -*-
"""BUG-2026-09-23-001：新增测试引入的三方依赖未钉入 app/requirements-test.txt，
CI unit-tests 收集期 ModuleNotFoundError → pytest-xdist 整批中断、main 留红。

实证（BUG-2026-09-22-015 的提交 1e0b08c 引入）：
tests/test_bug_2026_09_22_015_dropdown_class_collision.py 使用
``from bs4 import BeautifulSoup``，但 beautifulsoup4 从未出现在
app/requirements-test.txt（CI unit-tests 唯一安装的依赖清单）。
作者本地环境恰好装了 bs4，本地 17 项全绿即推送（R8 实证形态：
"本地看着绿就推送"）；CI 容器无 bs4 → 收集期
``ModuleNotFoundError: No module named 'bs4'`` → ``Interrupted: 1 error
during collection`` → WMS CI #1208 unit-tests 红，§三 CI 全绿门禁被破。

本测试即 R8 回归锁：全量扫描 tests/ 顶层 import，把"项目本地模块"与
"三方包"分开，凡三方包必须能在 app/requirements-test.txt（含 -r 链）
中找到钉版记录；任何新增未钉测试依赖都会让本测试精准变红。
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"
REQ_TEST = ROOT / "app" / "requirements-test.txt"

# 项目本地模块的搜索落点（与 pytest/conftest 的 sys.path 语义一致）
_LOCAL_BASES = (ROOT, ROOT / "app", ROOT / "scripts", ROOT / "tests", ROOT / "tools")

# import 名 → pip 包名（仅列两者不一致的；一致走原名）
_IMPORT_TO_PKG = {
    "bs4": "beautifulsoup4",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "cv2": "opencv-python",
    "Crypto": "pycryptodome",
    "dateutil": "python-dateutil",
    "fitz": "pymupdf",
    "docx": "python-docx",
    "flask_login": "flask-login",
    "flask_wtf": "flask-wtf",
    "flask_sqlalchemy": "flask-sqlalchemy",
    "flask_migrate": "flask-migrate",
    "flask_cors": "flask-cors",
    "xdist": "pytest-xdist",
    "MySQLdb": "mysqlclient",
    "sklearn": "scikit-learn",
}

# 项目自身顶层包（永远不算三方依赖）
_PROJECT_TOP = {"app", "conftest", "tests"}


def _norm(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _declared_packages() -> set:
    """解析 requirements-test.txt（递归跟随 -r 链），返回规范化包名集合。"""
    seen_files = set()
    pkgs = set()

    def _load(path: Path) -> None:
        path = path.resolve()
        if path in seen_files or not path.exists():
            return
        seen_files.add(path)
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("-r") or line.startswith("--requirement"):
                _load(path.parent / line.split(None, 1)[1].strip())
                continue
            if line.startswith("-"):
                continue
            name = re.split(r"[<>=!~\[;\s]", line, maxsplit=1)[0]
            if name:
                pkgs.add(_norm(name))

    _load(REQ_TEST)
    return pkgs


def _is_local_module(top: str) -> bool:
    """top 级模块名是否能在项目内找到落点（.py 文件或包/命名空间目录）。"""
    for base in _LOCAL_BASES:
        if (base / f"{top}.py").is_file():
            return True
        if (base / top).is_dir():  # 含 __init__.py 的包与 PEP 420 命名空间包
            return True
    return False


def _third_party_imports(path: Path):
    """产出 (行号, 顶层模块名)。只统计绝对 import，跳过相对 import。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, ValueError):
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # 相对 import 属项目内部
                continue
            if node.module:
                yield node.lineno, node.module.split(".")[0]


def _collect_missing():
    """返回 [(test_file, line, top_module, pip_pkg)] 形式的未钉依赖清单。"""
    declared = _declared_packages()
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    missing = []
    for f in sorted(TESTS_DIR.rglob("*.py")):
        for lineno, top in _third_party_imports(f):
            if not top or top in _PROJECT_TOP or top in stdlib:
                continue
            if _is_local_module(top):
                continue
            pkg = _norm(_IMPORT_TO_PKG.get(top, top))
            if pkg not in declared:
                missing.append((f.relative_to(ROOT).as_posix(), lineno, top, pkg))
    return missing


def test_requirements_test_txt_exists():
    """T0：测试依赖清单本身必须存在（清单丢了扫描就失去基准）。"""
    assert REQ_TEST.is_file(), f"缺少 {REQ_TEST.relative_to(ROOT)}"


def test_all_third_party_imports_pinned():
    """T1（回归锁）：tests/ 全部三方 import 必须被 requirements-test.txt 钉住。"""
    missing = _collect_missing()
    assert not missing, (
        "以下测试依赖未钉入 app/requirements-test.txt，CI unit-tests 会在收集期炸：\n"
        + "\n".join(
            f"  {f}:{ln}  import {top}  →  缺 pip 包 {pkg}"
            for f, ln, top, pkg in missing
        )
        + "\n修复：把对应包以「包名==版本」钉入 app/requirements-test.txt。"
    )


def test_no_bare_import_of_known_unpinned(caplog=None):
    """T2（结构守护）：requirements-test.txt 每行依赖必须带 == 钉版。

    只钉包名不钉版本，等于把"拉最新版"的版本漂移风险（CI-ENV-2026-09-11
    要杜绝的东西）又请回来。
    """
    offenders = []
    for raw in REQ_TEST.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        if "==" not in line:
            offenders.append(line)
    assert not offenders, (
        "app/requirements-test.txt 存在未钉版本的依赖（必须 包名==版本）："
        f"{offenders}"
    )
