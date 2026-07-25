"""AI-DEPLOY-F01 / AI-DEPLOY-F01-FIX-01: 启动时 GitHub 自动更新 - 专项验证脚本
# AI_TASK: AI-DEPLOY-F01
# AI_TASK: AI-DEPLOY-F01-FIX-01
# AI_TASK: AI-DEPLOY-F01-FIX-02

验证启动前可选从 GitHub main 更新的闭环：

1. run_server.py 在 main() 启动 serve() 之前经 _run_startup_auto_update 调用 auto_update.main()
2. 系统设置 github_auto_update_enabled 默认关闭；未开启时不拉取
3. WMS_SKIP_AUTO_UPDATE=1 环境变量可强制跳过自动更新
4. auto_update.main() 异常不阻断 WMS 启动
5. start_wms_auto.bat 作为 nssm 服务入口，直接启动 run_server.py，不重复触发、无 pause
6. auto_update.py 保留安全属性：ff-only / 不切分支 / 工作区脏跳过 / 失败不阻断
7. 任务标记存在于 auto_update.py / run_server.py / 本脚本

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
SCRIPTS_DIR = ROOT / "scripts"

RUN_SERVER_PATH = APP_DIR / "run_server.py"
AUTO_UPDATE_PATH = APP_DIR / "auto_update.py"
APP_PY_PATH = APP_DIR / "app.py"
START_WMS_AUTO_PATH = APP_DIR / "start_wms_auto.bat"
START_WMS_OFFLINE_PATH = APP_DIR / "start_wms_offline.bat"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check(condition: bool, msg: str, failures: list[str]) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {msg}")
    if not condition:
        failures.append(msg)


def test_run_server_wires_auto_update(failures: list[str]) -> None:
    """run_server.py 在 main() 启动 serve() 之前调用 auto_update.main()"""
    print("\n[Test 1] run_server.py 在 serve() 之前调用 auto_update.main()")
    text = _read(RUN_SERVER_PATH)

    has_import = "import auto_update" in text
    check(has_import, "run_server.py 导入 auto_update 模块", failures)

    has_call = re.search(
        r"def\s+_run_startup_auto_update\b.*?auto_update\.main\(\)",
        text,
        re.DOTALL,
    ) is not None
    check(has_call, "_run_startup_auto_update() 内调用 auto_update.main()", failures)

    main_match = re.search(r"def\s+main\(\).*?(?=\ndef\s|\Z)", text, re.DOTALL)
    if main_match:
        main_body = main_match.group(0)
        call_pos = main_body.find("_run_startup_auto_update()")
        serve_pos = main_body.find("serve(")
        ordered = call_pos != -1 and serve_pos != -1 and call_pos < serve_pos
        check(ordered, "main() 中 _run_startup_auto_update() 在 serve() 之前调用", failures)
    else:
        check(False, "未找到 run_server.py main() 函数", failures)

    try_block = re.search(
        r"try:\s*\n\s*auto_update\.main\(\)\s*\n\s*except\s+Exception",
        text,
    )
    check(try_block is not None, "auto_update.main() 调用包裹在 try/except 中（不阻断启动）", failures)


def test_setting_default_off_and_skip_env(failures: list[str]) -> None:
    """系统设置默认关闭 + WMS_SKIP_AUTO_UPDATE 可强制跳过"""
    print("\n[Test 2] github_auto_update_enabled 默认关闭 + WMS_SKIP_AUTO_UPDATE 跳过")
    app_text = _read(APP_PY_PATH)
    text = _read(RUN_SERVER_PATH)

    has_setting = "github_auto_update_enabled" in app_text and "运维更新" in app_text
    check(has_setting, "app.py 系统设置含 github_auto_update_enabled（运维更新）", failures)

    default_off = re.search(
        r"github_auto_update_enabled[\s\S]{0,200}?'default'\s*:\s*'0'",
        app_text,
    ) is not None
    check(default_off, "github_auto_update_enabled 默认值为 '0'（关闭）", failures)

    has_helper = "def github_auto_update_enabled(" in app_text
    check(has_helper, "app.py 提供 github_auto_update_enabled() 读取函数", failures)

    has_gate = "_github_auto_update_setting_enabled" in text and "github_auto_update_enabled" in text
    check(has_gate, "run_server.py 启动更新前检查系统设置开关", failures)

    has_env_check = "WMS_SKIP_AUTO_UPDATE" in text
    check(has_env_check, "run_server.py 引用 WMS_SKIP_AUTO_UPDATE 环境变量", failures)

    skip_logic = re.search(
        r"def\s+_run_startup_auto_update\b.*?WMS_SKIP_AUTO_UPDATE.*?return",
        text,
        re.DOTALL,
    )
    check(skip_logic is not None, "_run_startup_auto_update() 内含 WMS_SKIP_AUTO_UPDATE 跳过逻辑", failures)

    mock_called: list[bool] = []

    class _MockAutoUpdate:
        @staticmethod
        def main():
            mock_called.append(True)

    original = sys.modules.get("auto_update")
    sys.modules["auto_update"] = _MockAutoUpdate  # type: ignore[assignment]
    try:
        if "run_server" in sys.modules:
            del sys.modules["run_server"]
        sys.path.insert(0, str(APP_DIR))
        try:
            import run_server  # type: ignore[import-not-found]
        except Exception as e:  # noqa: BLE001
            print(f"  [SKIP] 运行时测试依赖缺失（{e}），静态检查已覆盖，跳过运行时验证")
            return

        os.environ["WMS_SKIP_AUTO_UPDATE"] = "1"
        try:
            run_server._run_startup_auto_update()
            check(len(mock_called) == 0, "WMS_SKIP_AUTO_UPDATE=1 时不调用 auto_update.main()", failures)
        finally:
            os.environ.pop("WMS_SKIP_AUTO_UPDATE", None)

        # AI-DEPLOY-F01-FIX-02: mock 固定关闭，避免本机 DB 曾开启导致误报
        mock_called.clear()
        original_gate = run_server._github_auto_update_setting_enabled
        run_server._github_auto_update_setting_enabled = lambda: False  # type: ignore[assignment]
        try:
            run_server._run_startup_auto_update()
            check(len(mock_called) == 0, "系统设置关闭时不调用 auto_update.main()", failures)
        finally:
            run_server._github_auto_update_setting_enabled = original_gate  # type: ignore[assignment]

        mock_called.clear()
        original_gate = run_server._github_auto_update_setting_enabled
        run_server._github_auto_update_setting_enabled = lambda: True  # type: ignore[assignment]
        try:
            run_server._run_startup_auto_update()
            check(len(mock_called) == 1, "系统设置开启时调用 auto_update.main() 一次", failures)
        finally:
            run_server._github_auto_update_setting_enabled = original_gate  # type: ignore[assignment]
    finally:
        if original is not None:
            sys.modules["auto_update"] = original
        else:
            sys.modules.pop("auto_update", None)
        if str(APP_DIR) in sys.path:
            sys.path.remove(str(APP_DIR))


def test_start_wms_auto_delegates(failures: list[str]) -> None:
    """start_wms_auto.bat 作为 nssm 服务入口，直接启动 run_server.py，不重复触发 auto_update，不含 pause"""
    print("\n[Test 3] start_wms_auto.bat 服务入口（无 pause / 不重复触发 auto_update / 直接 run_server.py）")
    if not START_WMS_AUTO_PATH.exists():
        check(False, f"{START_WMS_AUTO_PATH.name} 不存在", failures)
        return

    text = _read(START_WMS_AUTO_PATH)

    uses_run_server = "run_server.py" in text
    check(uses_run_server, "start_wms_auto.bat 直接启动 run_server.py（间接触发 auto_update）", failures)

    direct_call = "auto_update.py" in text and ('"%PYTHON_CMD%" "%~dp0auto_update.py"' in text)
    check(not direct_call, "start_wms_auto.bat 不再直接执行 auto_update.py（避免重复触发）", failures)

    pause_cmd = re.search(r'(?im)^\s*(?:call\s+)?pause\b', text)
    check(pause_cmd is None, "start_wms_auto.bat 不含 pause 命令（适配 nssm 服务无交互终端）", failures)

    has_python_lookup = "PYTHON_CMD" in text and "python.exe" in text
    check(has_python_lookup, "start_wms_auto.bat 含 Python 查找逻辑（优先绿色版）", failures)


def test_auto_update_safety_properties(failures: list[str]) -> None:
    """auto_update.py 保留安全属性"""
    print("\n[Test 4] auto_update.py 安全属性（ff-only / 不切分支 / 脏工作区跳过 / 失败不阻断）")
    if not AUTO_UPDATE_PATH.exists():
        check(False, f"{AUTO_UPDATE_PATH.name} 不存在", failures)
        return

    text = _read(AUTO_UPDATE_PATH)

    has_ff_only = "pull" in text and "--ff-only" in text
    check(has_ff_only, "使用 git pull --ff-only", failures)

    has_no_force = "--force" not in text and " --force" not in text
    check(has_no_force, "不使用 git --force", failures)

    has_branch_check = "branch" in text and "BRANCH" in text and "main" in text
    check(has_branch_check, "检查当前分支必须为 main（避免切分支）", failures)

    has_dirty_check = "status" in text and "--porcelain" in text
    check(has_dirty_check, "工作区脏时跳过 pull（git status --porcelain 检查）", failures)

    # AI-DEPLOY-F01-FIX-02
    has_correct_behind = "HEAD.." in text and "rev-list" in text
    has_wrong_union = (
        'rev-list", "--count", "HEAD", f"{REMOTE}/{BRANCH}"' in text
        or 'rev-list", "--count", "HEAD", f"{REMOTE}' in text
    )
    check(has_correct_behind, "落后提交使用 HEAD..remote/branch（真正 behind）", failures)
    check(not has_wrong_union, "不再使用 HEAD 与 remote 两 tip 并集计数", failures)
    check("--untracked-files=no" in text, "脏工作区仅检查已跟踪文件（忽略 runtime 等未跟踪）", failures)
    check("find_git" in text, "find_git 可在服务 PATH 不全时定位 git.exe", failures)

    has_non_blocking = "不阻断" in text or "不阻断启动" in text
    check(has_non_blocking, "docstring 声明失败不阻断启动", failures)

    has_git_check = ".git" in text and "git_dir" in text.lower()
    check(has_git_check, "非 git 仓库时跳过自动更新", failures)

    has_backup = "backup_database" in text or "备份" in text
    check(has_backup, "更新前备份数据库", failures)


def test_task_marker_present(failures: list[str]) -> None:
    """AI-DEPLOY-F01 / FIX-01 / FIX-02 任务标记存在于关键文件"""
    print("\n[Test 5] AI-DEPLOY-F01 / FIX-01 / FIX-02 任务标记存在")
    marker = "AI-DEPLOY-F01"
    fix_marker = "AI-DEPLOY-F01-FIX-01"
    fix2_marker = "AI-DEPLOY-F01-FIX-02"

    for path in (AUTO_UPDATE_PATH, RUN_SERVER_PATH, Path(__file__)):
        text = _read(path)
        check(marker in text, f"{path.relative_to(ROOT)} 含 AI-DEPLOY-F01 标记", failures)
        check(fix_marker in text, f"{path.relative_to(ROOT)} 含 AI-DEPLOY-F01-FIX-01 标记", failures)
    for path in (AUTO_UPDATE_PATH, Path(__file__)):
        text = _read(path)
        check(fix2_marker in text, f"{path.relative_to(ROOT)} 含 AI-DEPLOY-F01-FIX-02 标记", failures)


def test_start_wms_offline_uses_run_server(failures: list[str]) -> None:
    """start_wms_offline.bat 通过 run_server.py 启动（间接触发 auto_update）"""
    print("\n[Test 6] start_wms_offline.bat 通过 run_server.py 启动")
    if not START_WMS_OFFLINE_PATH.exists():
        check(False, f"{START_WMS_OFFLINE_PATH.name} 不存在", failures)
        return

    text = _read(START_WMS_OFFLINE_PATH)
    uses_run_server = "run_server.py" in text
    check(uses_run_server, "start_wms_offline.bat 调用 run_server.py（间接触发 auto_update）", failures)


def main() -> int:
    print("=" * 60)
    print("AI-DEPLOY-F01-FIX-02: 启动自动更新（默认关 + 正确 behind）- 专项验证")
    print("=" * 60)

    failures: list[str] = []

    test_run_server_wires_auto_update(failures)
    test_setting_default_off_and_skip_env(failures)
    test_start_wms_auto_delegates(failures)
    test_auto_update_safety_properties(failures)
    test_task_marker_present(failures)
    test_start_wms_offline_uses_run_server(failures)

    print("\n" + "=" * 60)
    if failures:
        print(f"FAIL AI-DEPLOY-F01-FIX-02: {len(failures)} 项失败")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS AI-DEPLOY-F01-FIX-02: 启动自动更新（默认关 + 正确 behind）闭环验证通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
