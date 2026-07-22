# -*- coding: utf-8 -*-
"""模块3黄金测试：install.bat + install_e_wms.bat 部署脚本合并基线。

# AI_TASK: 部署脚本合并 黄金测试（绞杀者模式前置基线）

所有断言严格依据《项目黑话词典》确定性语义与 AGENTS.md 密码透明性约束，禁止使用通用 WMS 术语。
本测试通过解析 .bat 脚本文本（不执行）确保合并后行为不变。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
INSTALL_BAT = WORKSPACE_ROOT / 'install.bat'
INSTALL_E_WMS_BAT = WORKSPACE_ROOT / 'install_e_wms.bat'


def _read_bat(path: Path) -> str:
    if not path.exists():
        pytest.skip(f'脚本不存在: {path}')
    return path.read_text(encoding='utf-8', errors='ignore')


# ----------------------------------------------------------------------
# 模块3-A：安装目录与 Python 部署模式差异基线
# ----------------------------------------------------------------------

# 依据：install.bat / install_e_wms.bat 确定性语义（INSTALL_DIR 必须可区分）
def test_install_dir_differs_between_two_scripts():
    """基线：install.bat 装到 C:\\WMS，install_e_wms.bat 装到 E:\\wms，合并后必须保留差异。"""
    install_text = _read_bat(INSTALL_BAT)
    e_wms_text = _read_bat(INSTALL_E_WMS_BAT)
    # install.bat: set "INSTALL_DIR=C:\WMS"
    assert re.search(r'set\s+"INSTALL_DIR=C:\\WMS"', install_text), (
        "install.bat 必须设置 INSTALL_DIR=C:\\WMS"
    )
    # install_e_wms.bat: set "INSTALL_DIR=E:\wms"
    assert re.search(r'set\s+"INSTALL_DIR=E:\\wms"', e_wms_text), (
        "install_e_wms.bat 必须设置 INSTALL_DIR=E:\\wms"
    )


# 依据：install.bat 确定性语义（系统 Python，PrependPath=1）
def test_install_bat_uses_system_python_with_path():
    """基线：install.bat 部署系统 Python（PrependPath=1，加入 PATH）。"""
    text = _read_bat(INSTALL_BAT)
    # PrependPath=1 表示加入系统 PATH
    assert 'PrependPath=1' in text, "install.bat 必须将 Python 加入系统 PATH"
    # 不设置 TargetDir（用默认安装路径）
    assert 'TargetDir=' not in text, "install.bat 不得设置自定义 TargetDir"


# 依据：install_e_wms.bat 确定性语义（便携 Python，PrependPath=0，TargetDir=install_dir\\python）
def test_install_e_wms_bat_uses_portable_python_without_path():
    """基线：install_e_wms.bat 部署便携 Python（PrependPath=0，TargetDir=PYTHON_DIR，不入 PATH）。"""
    text = _read_bat(INSTALL_E_WMS_BAT)
    assert 'PrependPath=0' in text, "install_e_wms.bat 不得将 Python 加入 PATH"
    assert 'TargetDir="%PYTHON_DIR%"' in text, (
        "install_e_wms.bat 必须设置 TargetDir=PYTHON_DIR（便携模式）"
    )
    # PYTHON_DIR = INSTALL_DIR\python
    assert re.search(r'set\s+"PYTHON_DIR=%INSTALL_DIR%\\python"', text), (
        "install_e_wms.bat 必须定义 PYTHON_DIR=%INSTALL_DIR%\\python"
    )


# 依据：install.bat / install_e_wms.bat 确定性语义（PYTHON_EXE 路径解析差异）
def test_python_exe_resolution_differs():
    """基线：两脚本 PYTHON_EXE 解析路径必须可区分。"""
    install_text = _read_bat(INSTALL_BAT)
    e_wms_text = _read_bat(INSTALL_E_WMS_BAT)
    # install.bat: 优先用 LocalAppData 或 ProgramFiles 系统 Python
    assert 'Programs\\Python\\Python311\\python.exe' in install_text, (
        "install.bat 必须解析系统 Python 路径"
    )
    # install_e_wms.bat: PYTHON_EXE = PYTHON_DIR\python.exe
    assert 'set "PYTHON_EXE=%PYTHON_DIR%\\python.exe"' in e_wms_text, (
        "install_e_wms.bat 必须解析便携 Python 路径"
    )


# ----------------------------------------------------------------------
# 模块3-B：共享行为基线（合并后必须保留）
# ----------------------------------------------------------------------

# 依据：install.bat / install_e_wms.bat 确定性语义（8 步流程顺序不可变）
@pytest.mark.parametrize('step_marker', [
    '[1/8]', '[2/8]', '[3/8]', '[4/8]', '[5/8]', '[6/8]', '[7/8]', '[8/8]',
])
def test_install_bat_eight_step_pipeline_present(step_marker):
    """基线：install.bat 8 步流程标记必须全部存在。"""
    text = _read_bat(INSTALL_BAT)
    assert step_marker in text, f"install.bat 必须包含 {step_marker} 步骤标记"


# 依据：install.bat / install_e_wms.bat 确定性语义（8 步流程顺序不可变）
@pytest.mark.parametrize('step_marker', [
    '[1/8]', '[2/8]', '[3/8]', '[4/8]', '[5/8]', '[6/8]', '[7/8]', '[8/8]',
])
def test_install_e_wms_bat_eight_step_pipeline_present(step_marker):
    """基线：install_e_wms.bat 8 步流程标记必须全部存在。"""
    text = _read_bat(INSTALL_E_WMS_BAT)
    assert step_marker in text, f"install_e_wms.bat 必须包含 {step_marker} 步骤标记"


# 依据：install.bat / install_e_wms.bat 确定性语义（wheelhouse 离线依赖安装）
def test_offline_wheelhouse_install_shared():
    """基线：两脚本均使用 --no-index --find-links wheelhouse 离线安装。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert '--no-index' in text, f"{path.name} 必须使用 --no-index 离线模式"
        assert '--find-links "%WHEELHOUSE%"' in text, (
            f"{path.name} 必须指向 WHEELHOUSE 目录"
        )
        assert 'requirements.txt' in text, f"{path.name} 必须安装 requirements.txt"


# 依据：install.bat / install_e_wms.bat 确定性语义（IN_PLACE_INSTALL 模式判定）
def test_in_place_install_detection_shared():
    """基线：两脚本必须实现 IN_PLACE_INSTALL 模式判定（PKG_DIR==INSTALL_DIR 时跳过拷贝）。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert 'IN_PLACE_INSTALL' in text, f"{path.name} 必须支持 IN_PLACE_INSTALL 判定"
        assert 'PKG_DIR_FULL' in text and 'INSTALL_DIR_FULL' in text, (
            f"{path.name} 必须通过 PKG_DIR_FULL==INSTALL_DIR_FULL 比较"
        )


# 依据：install.bat / install_e_wms.bat 确定性语义（业务数据库保护：包内含 inventory.db 拒绝安装）
def test_business_database_protection_shared():
    """基线：包内含 instance\\inventory.db 时必须拒绝安装。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert 'Package contains a business database and will not install' in text, (
            f"{path.name} 必须拒绝安装含业务数据库的包"
        )
        assert 'instance\\inventory.db' in text, (
            f"{path.name} 必须检测 instance\\inventory.db"
        )


# 依据：install.bat / install_e_wms.bat 确定性语义（启动前停止旧 WMS 进程）
def test_stop_old_wms_process_shared():
    """基线：两脚本必须先停止旧 WMS 进程（8080 端口）。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert 'Stopping old WMS process' in text, f"{path.name} 必须停止旧进程"
        assert 'LocalPort 8080' in text, f"{path.name} 必须按 8080 端口停止进程"


# 依据：install.bat / install_e_wms.bat 确定性语义（数据库初始化命令相同）
def test_database_initialization_command_shared():
    """基线：两脚本必须用相同 Python 一行命令初始化数据库。"""
    expected_cmd = (
        'from app import app, initialize_database; '
        'ctx=app.app_context(); ctx.push(); initialize_database(); ctx.pop()'
    )
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert expected_cmd in text, f"{path.name} 必须用相同初始化命令"


# 依据：install.bat / install_e_wms.bat 确定性语义（WMS_ALLOW_AUTO_SECRET_KEY=1 / WMS_INIT_SAMPLE_DATA=0）
def test_env_vars_for_init_shared():
    """基线：两脚本初始化时必须设置 WMS_ALLOW_AUTO_SECRET_KEY=1 和 WMS_INIT_SAMPLE_DATA=0。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert 'WMS_ALLOW_AUTO_SECRET_KEY=1' in text, (
            f"{path.name} 必须设置 WMS_ALLOW_AUTO_SECRET_KEY=1"
        )
        assert 'WMS_INIT_SAMPLE_DATA=0' in text, (
            f"{path.name} 必须设置 WMS_INIT_SAMPLE_DATA=0（不灌入样例数据）"
        )


# ----------------------------------------------------------------------
# 模块3-C：AGENTS.md 密码透明性约束基线
# ----------------------------------------------------------------------

# 依据：AGENTS.md 密码透明性约束（禁用 secrets.token_urlsafe 等随机生成器）
def test_no_random_password_generator_in_install_scripts():
    """基线：两脚本不得调用任何随机密码生成器（secrets/token_urlsafe/random）。"""
    forbidden_patterns = ['secrets.token_urlsafe', 'token_urlsafe', 'os.urandom', 'random.']
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        for pattern in forbidden_patterns:
            assert pattern not in text, (
                f"{path.name} 不得包含随机密码生成器: {pattern}"
            )


# 依据：AGENTS.md 密码透明性约束（WMS_BOOTSTRAP_PASSWORD 未设置时用固定默认密码 admin）
def test_install_bat_default_password_message_compliant():
    """基线：install.bat 必须显式提示 'admin' 默认密码（不得使用随机密码）。"""
    text = _read_bat(INSTALL_BAT)
    assert 'WMS_BOOTSTRAP_PASSWORD' in text, "install.bat 必须提及 WMS_BOOTSTRAP_PASSWORD 环境变量"
    assert 'admin' in text, "install.bat 必须显式提示默认密码 admin"


# 依据：AGENTS.md 密码透明性约束（WMS_BOOTSTRAP_PASSWORD 未设置时用固定默认密码 admin）
def test_install_e_wms_bat_default_password_message_compliant():
    """基线：install_e_wms.bat 必须显式提示 'admin' 默认密码（不得使用随机密码）。"""
    text = _read_bat(INSTALL_E_WMS_BAT)
    assert 'WMS_BOOTSTRAP_PASSWORD' in text, (
        "install_e_wms.bat 必须提及 WMS_BOOTSTRAP_PASSWORD 环境变量"
    )
    assert 'admin' in text, "install_e_wms.bat 必须显式提示默认密码 admin"


# 依据：AGENTS.md 密码透明性约束（不得设置/修改/重置任何账户密码）
def test_install_scripts_do_not_set_password_directly():
    """基线：两脚本不得直接 set/pass 密码到 Python 进程（避免在脚本中固化密码）。"""
    forbidden_patterns = [
        r'set\s+"WMS_BOOTSTRAP_PASSWORD=',  # 不得在脚本中硬设密码
        r'--password',
        r'ADMIN_PASSWORD',
    ]
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        for pattern in forbidden_patterns:
            assert not re.search(pattern, text), (
                f"{path.name} 不得直接设置密码: 匹配 {pattern}"
            )


# ----------------------------------------------------------------------
# 模块3-D：start_wms_offline.bat 启动脚本依赖基线
# ----------------------------------------------------------------------

# 依据：install.bat / install_e_wms.bat 确定性语义（必须检查 start_wms_offline.bat 存在）
def test_install_scripts_check_start_wms_offline_bat():
    """基线：两脚本必须检查 start_wms_offline.bat 存在，缺失则报错退出。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert 'start_wms_offline.bat' in text, f"{path.name} 必须依赖 start_wms_offline.bat"
        assert 'start_wms_offline.bat not found' in text, (
            f"{path.name} 缺失启动脚本时必须报错退出"
        )


# 依据：install.bat / install_e_wms.bat 确定性语义（IN_PLACE_INSTALL 模式下 START_SCRIPT 路径不同）
def test_start_script_path_differs_in_in_place_mode():
    """基线：IN_PLACE_INSTALL=1 时 START_SCRIPT=%PKG_DIR%\\start_wms_offline.bat。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert 'START_SCRIPT=%PKG_DIR%\\start_wms_offline.bat' in text, (
            f"{path.name} IN_PLACE_INSTALL=1 时必须指向 PKG_DIR 下的启动脚本"
        )
        assert 'START_SCRIPT=%INSTALL_DIR%\\start_wms_offline.bat' in text, (
            f"{path.name} 非 IN_PLACE_INSTALL 时必须指向 INSTALL_DIR 下的启动脚本"
        )


# ----------------------------------------------------------------------
# 模块3-E：桌面快捷方式创建基线
# ----------------------------------------------------------------------

# 依据：install.bat / install_e_wms.bat 确定性语义（创建 WMS.lnk 桌面快捷方式）
def test_desktop_shortcut_creation_shared():
    """基线：两脚本必须创建 WMS.lnk 桌面快捷方式。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert 'WMS.lnk' in text, f"{path.name} 必须创建 WMS.lnk 快捷方式"
        assert 'WScript.Shell' in text, f"{path.name} 必须用 WScript.Shell 创建快捷方式"
        assert "TargetPath='%START_SCRIPT%'" in text, (
            f"{path.name} 快捷方式 TargetPath 必须指向 START_SCRIPT"
        )


# ----------------------------------------------------------------------
# 模块3-F：错误退出码基线
# ----------------------------------------------------------------------

# 依据：install.bat / install_e_wms.bat 确定性语义（失败时 exit /b 1）
def test_error_exit_code_one_on_failure():
    """基线：两脚本失败时必须 exit /b 1，成功时 exit /b 0。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert 'exit /b 1' in text, f"{path.name} 失败路径必须 exit /b 1"
        assert text.rstrip().endswith('exit /b 0'), f"{path.name} 末尾必须 exit /b 0"


# 依据：install.bat / install_e_wms.bat 确定性语义（包完整性检查 app\\app.py）
def test_package_completeness_check_shared():
    """基线：两脚本必须检查 app\\app.py 存在，缺失则报错退出。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert 'app\\app.py not found' in text, f"{path.name} 必须检查 app\\app.py"
        assert 'wheelhouse not found' in text, f"{path.name} 必须检查 wheelhouse 目录"


# ----------------------------------------------------------------------
# 模块3-G：备份行为基线
# ----------------------------------------------------------------------

# 依据：install.bat / install_e_wms.bat 确定性语义（安装前备份 inventory.db）
def test_backup_inventory_db_before_install_shared():
    """基线：两脚本必须在安装前备份 instance\\inventory.db 到 backups 目录。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        assert 'before_offline_install_' in text, f"{path.name} 必须命名备份文件"
        assert 'backups\\' in text, f"{path.name} 必须备份到 backups 目录"
        assert 'copy /Y' in text, f"{path.name} 必须用 copy /Y 覆盖备份"


# 依据：install.bat / install_e_wms.bat 确定性语义（创建 logs/backups/instance 目录）
def test_create_runtime_directories_shared():
    """基线：两脚本必须创建 logs/backups/instance 三个运行时目录。"""
    for path in (INSTALL_BAT, INSTALL_E_WMS_BAT):
        text = _read_bat(path)
        for dirname in ('logs', 'backups', 'instance'):
            assert f'\\{dirname}"' in text or f'\\{dirname}' in text, (
                f"{path.name} 必须创建 {dirname} 目录"
            )
