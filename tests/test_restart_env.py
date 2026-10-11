# -*- coding: utf-8 -*-
"""回归守卫：restart.py 的生产环境构造（2026-10-11 更新脚本启动失败事故）。

事故根因：update_from_github.bat 第 [6/6] 步调用 restart.py 拉起服务，但
restart.py 未设置 WMS_ALLOW_INSECURE_COOKIE，而本部署为 127.0.0.1:8080 HTTP，
config.validate_production_security_config 于是在 import 阶段直接 RuntimeError，
服务静默起不来——更新脚本"成功"跑完，却没有任何服务在监听。

start_wms_offline.bat 设了该变量，restart.py / run_wms_task.bat 漏了；本测试
锁死 restart.py 的行为，防止再次回归。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import restart  # noqa: E402


def test_build_server_env():
    """核心回归：无 SESSION_COOKIE_SECURE 时必须默认放行非 Secure Cookie。"""
    env = restart.build_server_env({})
    assert env["FLASK_ENV"] == "production"
    assert env["PYTHONUTF8"] == "1"
    assert env["WMS_ALLOW_AUTO_SECRET_KEY"] == "1"
    assert env["WMS_ALLOW_INSECURE_COOKIE"] == "1", (
        "restart.py 未放行非 Secure Cookie：生产模式 import 阶段会 RuntimeError，"
        "update_from_github.bat 第 [6/6] 步启动失败（2026-10-11 事故）"
    )


def test_build_server_env_https_deployment_not_forced_insecure():
    """HTTPS 部署（SESSION_COOKIE_SECURE=true）不应被强塞非 Secure 放行。"""
    env = restart.build_server_env({"SESSION_COOKIE_SECURE": "true"})
    assert "WMS_ALLOW_INSECURE_COOKIE" not in env


def test_build_server_env_respects_explicit_optin():
    """操作员显式设过 WMS_ALLOW_INSECURE_COOKIE 时不得覆盖其值。"""
    env = restart.build_server_env({"WMS_ALLOW_INSECURE_COOKIE": "0"})
    assert env["WMS_ALLOW_INSECURE_COOKIE"] == "0"


def test_build_server_env_respects_explicit_secret_key_optin():
    """WMS_ALLOW_AUTO_SECRET_KEY 已显式设置时保持原值。"""
    env = restart.build_server_env({"WMS_ALLOW_AUTO_SECRET_KEY": "0"})
    assert env["WMS_ALLOW_AUTO_SECRET_KEY"] == "0"


def test_build_server_env_does_not_mutate_base():
    """不得就地修改传入的 base_env（main 传入的是 os.environ）。"""
    base = {"FOO": "bar"}
    restart.build_server_env(base)
    assert base == {"FOO": "bar"}
