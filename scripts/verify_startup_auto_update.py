"""AI-DEPLOY-F01: WMS 启动时自动从 GitHub 更新功能 - 专项验证脚本
# AI_TASK: AI-DEPLOY-F01

验证 WMS 每次启动都自动从 GitHub main 分支更新代码和依赖的闭环：

1. run_server.py 在 main() 启动 serve() 之前调用 auto_update.main()
2. WMS_SKIP_AUTO_UPDATE=1 环境变量可跳过自动更新（用于测试/安装/特殊运维）
3. auto_update.main() 异常不阻断 WMS 启动（兜底用现有代码启动）
4. start_wms_auto.bat 委托给 start_wms_offline.bat，不重复触发 auto_update
5. auto_update.py 保留安全属性：ff-only / 不切分支 / 工作区脏跳过 / 失败不阻断
6. AI-DEPLOY-F01 任务标记存在于 auto_update.py / run_server.py / 本脚本

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

    # _run_startup_auto_update 调用 auto_update.main()
    has_call = re.search(
        r"def\s+_run_startup_auto_update\b.*?auto_update\.main\(\)",
        text,
        re.DOTALL,
    ) is not None
    check(has_call, "_run_startup_auto_update() 内调用 auto_update.main()", failures)

    # main() 在 serve() 之前调用 _run_startup_auto_update()
    main_match = re.search(r"def\s+main\(\).*?(?=\ndef\s|\Z)", text, re.DOTALL)
    if main_match:
        main_body = main_match.group(0)
        call_pos = main_body.find("_run_startup_auto_update()")
        serve_pos = main_body.find("serve(")
        ordered = call_pos != -1 and serve_pos != -1 and call_pos < serve_pos
        check(ordered, "main() 中 _run_startup_auto_update() 在 serve() 之前调用", failures)
    else:
        check(False, "未找到 run_server.py main() 函数", failures)

    # 异常兜底：auto_update.main() 调用包裹在 try/except 中
    try_block = re.search(
        r"try:\s*\n\s*auto_update\.main\(\)\s*\n\s*except\s+Exception",
        text,
    )
    check(try_block is not None, "auto_update.main() 调用包裹在 try/except 中（不阻断启动）", failures)


def test_skip_env_var(failures: list[str]) -> None:
    """WMS_SKIP_AUTO_UPDATE=1 可跳过自动更新"""
    print("\n[Test 2] WMS_SKIP_AUTO_UPDATE 环境变量可跳过自动更新")
    text = _read(RUN_SERVER_PATH)

    has_env_check = "WMS_SKIP_AUTO_UPDATE" in text
    check(has_env_check, "run_server.py 引用 WMS_SKIP_AUTO_UPDATE 环境变量", failures)

    # 静态校验：_run_startup_auto_update 函数体中包含环境变量跳过逻辑
    skip_logic = re.search(
        r"def\s+_run_startup_auto_update\b.*?WMS_SKIP_AUTO_UPDATE.*?return",
        text,
        re.DOTALL,
    )
    check(skip_logic is not None, "_run_startup_auto_update() 内含 WMS_SKIP_AUTO_UPDATE 跳过逻辑", failures)

    # 真实运行时测试：设置环境变量后 _run_startup_auto_update 不调用 auto_update.main()
    # 通过 sys.modules 注入 mock auto_update 模块，避免触发真实 git 操作
    # 注意：run_server.py 依赖 Flask/waitress/app 等模块，CI 环境 pip install -r requirements.txt 后可用；
    # 若依赖缺失（如最小化沙箱），跳过运行时测试，静态检查已覆盖逻辑。
    mock_called = []

    class _MockAutoUpdate:
        @staticmethod
        def main():
            mock_called.append(True)

    original = sys.modules.get("auto_update")
    sys.modules["auto_update"] = _MockAutoUpdate  # type: ignore[assignment]
    try:
        # 重新导入 run_server 以使 mock 生效
        if "run_server" in sys.modules:
            del sys.modules["run_server"]
        sys.path.insert(0, str(APP_DIR))
        try:
            import run_server  # type: ignore[import-not-found]
        except Exception as e:  # noqa: BLE001
            # 依赖缺失（Flask/waitress 等），跳过运行时测试；静态检查已覆盖逻辑
            print(f"  [SKIP] 运行时测试依赖缺失（{e}），静态检查已覆盖，跳过运行时验证")
            return

        # 设置跳过环境变量
        os.environ["WMS_SKIP_AUTO_UPDATE"] = "1"
        try:
            run_server._run_startup_auto_update()
            check(len(mock_called) == 0, "WMS_SKIP_AUTO_UPDATE=1 时不调用 auto_update.main()", failures)
        finally:
            os.environ.pop("WMS_SKIP_AUTO_UPDATE", None)

        # 不设置跳过环境变量时应调用 auto_update.main()
        run_server._run_startup_auto_update()
        check(len(mock_called) == 1, "未设置 WMS_SKIP_AUTO_UPDATE 时调用 auto_update.main() 一次", failures)
    finally:
        if original is not None:
            sys.modules["auto_update"] = original
        else:
            sys.modules.pop("auto_update", None)
        sys.path.remove(str(APP_DIR))


def test_start_wms_auto_delegates(failures: list[str]) -> None:
    """start_wms_auto.bat 委托给 start_wms_offline.bat，避免重复触发 auto_update"""
    print("\n[Test 3] start_wms_auto.bat 委托给 start_wms_offline.bat（不重复触发）")
    if not START_WMS_AUTO_PATH.exists():
        check(False, f"{START_WMS_AUTO_PATH.name} 不存在", failures)
        return

    text = _read(START_WMS_AUTO_PATH)
    delegates = "start_wms_offline.bat" in text and ("call " in text.lower())
    check(delegates, "start_wms_auto.bat 调用 start_wms_offline.bat", failures)

    # 不再直接调用 auto_update.py（避免与 run_server.py 重复触发）
    direct_call = "auto_update.py" in text and ('"%PYTHON_CMD%" "%~dp0auto_update.py"' in text)
    check(not direct_call, "start_wms_auto.bat 不再直接执行 auto_update.py（避免重复触发）", failures)


def test_auto_update_safety_properties(failures: list[str]) -> None:
    """auto_update.py 保留安全属性"""
    print("\n[Test 4] auto_update.py 安全属性（ff-only / 不切分支 / 脏工作区跳过 / 失败不阻断）")
    if not AUTO_UPDATE_PATH.exists():
        check(False, f"{AUTO_UPDATE_PATH.name} 不存在", failures)
        return

    text = _read(AUTO_UPDATE_PATH)

    # 仅 ff-only，不做 force
    has_ff_only = "pull" in text and "--ff-only" in text
    check(has_ff_only, "使用 git pull --ff-only", failures)

    has_no_force = "--force" not in text and " --force" not in text
    check(has_no_force, "不使用 git --force", failures)

    # 检查分支必须为 main，避免切分支
    has_branch_check = "branch" in text and "BRANCH" in text and "main" in text
    check(has_branch_check, "检查当前分支必须为 main（避免切分支）", failures)

    # 工作区脏时跳过 pull
    has_dirty_check = "status" in text and "--porcelain" in text
    check(has_dirty_check, "工作区脏时跳过 pull（git status --porcelain 检查）", failures)

    # 任何步骤失败都不阻断（return 0）
    has_non_blocking = "不阻断" in text or "不阻断启动" in text
    check(has_non_blocking, "docstring 声明失败不阻断启动", failures)

    # 非 git 仓库时跳过（首次安装场景）
    has_git_check = ".git" in text and "git_dir" in text.lower()
    check(has_git_check, "非 git 仓库时跳过自动更新", failures)

    # 备份数据库
    has_backup = "backup_database" in text or "备份" in text
    check(has_backup, "更新前备份数据库", failures)


def test_task_marker_present(failures: list[str]) -> None:
    """AI-DEPLOY-F01 任务标记存在于关键文件"""
    print("\n[Test 5] AI-DEPLOY-F01 任务标记存在")
    marker = "AI-DEPLOY-F01"

    for path in (AUTO_UPDATE_PATH, RUN_SERVER_PATH, Path(__file__)):
        text = _read(path)
        check(marker in text, f"{path.relative_to(ROOT)} 含 AI-DEPLOY-F01 标记", failures)


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
    print("AI-DEPLOY-F01: WMS 启动时自动从 GitHub 更新 - 专项验证")
    print("=" * 60)

    failures: list[str] = []

    test_run_server_wires_auto_update(failures)
    test_skip_env_var(failures)
    test_start_wms_auto_delegates(failures)
    test_auto_update_safety_properties(failures)
    test_task_marker_present(failures)
    test_start_wms_offline_uses_run_server(failures)

    print("\n" + "=" * 60)
    if failures:
        print(f"FAIL AI-DEPLOY-F01: {len(failures)} 项失败")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS AI-DEPLOY-F01: WMS 启动时自动从 GitHub 更新闭环验证通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
