#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/print_agent/wms_print_agent.py 纯函数单测（PRINT-ROUTING-F01-P3）。

只覆盖无副作用的辅助函数（URL 拼接 / 状态映射 / JSON 解析 / 配置合并），
浏览器与 PowerShell 交互属 Windows 运行时行为，不在 CI 覆盖范围。
"""
import argparse
import importlib.util
import json
import os

import pytest

_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "tools", "print_agent", "wms_print_agent.py")
_spec = importlib.util.spec_from_file_location("wms_print_agent", _SCRIPT)
agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agent)


def _args(**kwargs):
    base = dict(server_url=None, token=None, config=None, poll_interval=None,
                heartbeat_interval=None, print_timeout=None, directed_printer=None)
    base.update(kwargs)
    return argparse.Namespace(**base)


class TestJoinUrl:
    def test_join_url_strips_slashes(self):
        assert agent._join_url("http://h:5000/", "/print_queue/api/v1/claim") == \
            "http://h:5000/print_queue/api/v1/claim"
        assert agent._join_url("http://h", "a/b") == "http://h/a/b"


class TestMapPrinterStatus:
    def test_offline_or_work_offline_is_error(self):
        assert agent._map_printer_status(7, False) == "error"
        assert agent._map_printer_status(3, True) == "error"

    def test_normal_states_are_ready(self):
        for status in (None, 3, 4, 5):
            assert agent._map_printer_status(status, False) == "ready"


class TestParseJson:
    def test_valid_and_invalid(self):
        assert agent._parse_json(b'{"status": "success"}') == {"status": "success"}
        assert agent._parse_json(b'not json') == {}
        assert agent._parse_json(b'[1,2]') == {}


class TestEnumeratePrinters:
    def test_non_windows_returns_none(self):
        """非 Windows 无法枚举（_run_powershell_status 全 False）→ 返回 None（=枚举失败），
        而非空列表，避免服务端把已有打印机误标 offline（BUG-2026-08-24-005）。"""
        if os.name == "nt":
            pytest.skip("仅验证非 Windows 环境的枚举失败行为")
        assert agent.enumerate_printers() is None

    def test_parses_single_printer_object(self, monkeypatch):
        """ConvertTo-Json 只有一台打印机时输出单个对象而非数组，必须能解析。"""
        monkeypatch.setattr(agent, "_run_powershell_status", lambda cmd: (True, json.dumps(
            {"Name": "HP LaserJet 1020", "Default": True,
             "PrinterStatus": 3, "WorkOffline": False})))
        printers = agent.enumerate_printers()
        assert printers == [{"system_name": "HP LaserJet 1020",
                             "status": "ready", "is_default": True}]

    def test_parses_multiple_printers_array(self, monkeypatch):
        monkeypatch.setattr(agent, "_run_powershell_status", lambda cmd: (True, json.dumps([
            {"Name": "HP", "Default": True, "PrinterStatus": 3, "WorkOffline": False},
            {"Name": "TSC", "Default": False, "PrinterStatus": 7, "WorkOffline": True},
        ])))
        printers = agent.enumerate_printers()
        assert [p["system_name"] for p in printers] == ["HP", "TSC"]
        assert printers[1]["status"] == "error"

    def test_falls_back_to_wmi_on_powershell2(self, monkeypatch):
        """BUG-2026-08-19-006：Win7 默认 PowerShell 2.0 无 Get-CimInstance，
        首选命令执行失败（ok=False）时必须回退 Get-WmiObject（PS2.0 可用）。"""
        calls = []

        def fake_run(command):
            calls.append(command)
            if "Get-CimInstance" in command:
                return False, ""  # PS2.0：Get-CimInstance 不识别，退出码非 0
            return True, json.dumps([
                {"Name": "HP", "Default": True, "PrinterStatus": 3,
                 "WorkOffline": False}])

        monkeypatch.setattr(agent, "_run_powershell_status", fake_run)
        printers = agent.enumerate_printers()
        assert printers == [{"system_name": "HP", "status": "ready",
                             "is_default": True}]
        assert len(calls) == 2
        assert "Get-WmiObject" in calls[1]

    def test_falls_back_to_csv_on_powershell2(self, monkeypatch):
        """PS 2.0 连 ConvertTo-Json 也没有，最终回退 ConvertTo-Csv 输出，
        由 _parse_printer_output 用 csv 模块解析（字符串 True/数字均需转换）。"""
        calls = []

        def fake_run(command):
            calls.append(command)
            if "ConvertTo-Csv" in command:
                return True, ('"Name","Default","PrinterStatus","WorkOffline"\r\n'
                              '"HP LaserJet 1020","True","3","False"\r\n'
                              '"TSC TTP-244","False","7","True"\r\n')
            return False, ""  # 两个 Json 命令均失败

        monkeypatch.setattr(agent, "_run_powershell_status", fake_run)
        printers = agent.enumerate_printers()
        assert printers == [
            {"system_name": "HP LaserJet 1020", "status": "ready",
             "is_default": True},
            {"system_name": "TSC TTP-244", "status": "error",
             "is_default": False},
        ]
        assert len(calls) == 3

    def test_returns_empty_list_when_no_printers(self, monkeypatch):
        """命令成功但本机确实无打印机 → []（可与失败 None 区分，此时上报空列表才对）。"""
        monkeypatch.setattr(agent, "_run_powershell_status", lambda cmd: (True, ""))
        assert agent.enumerate_printers() == []

    def test_returns_none_when_all_commands_fail(self, monkeypatch):
        """三条命令全部失败（Print Spooler 停止/WMI 异常）→ None，不得误当「无打印机」。"""
        monkeypatch.setattr(agent, "_run_powershell_status", lambda cmd: (False, ""))
        assert agent.enumerate_printers() is None


class TestSendHeartbeat:
    """BUG-2026-08-24-005：枚举失败时上报 printers=None（非空列表），并按状态翻转节流告警。"""

    def _cfg(self):
        return {"server_url": "http://h", "token": "t"}

    def test_enum_failure_sends_null_and_throttles(self, monkeypatch, caplog):
        import logging
        sent = []
        monkeypatch.setattr(agent, "enumerate_printers", lambda: None)
        monkeypatch.setattr(agent, "api_call",
                            lambda *a: sent.append(a[3]) or (200, {"status": "success", "data": {}}))
        monkeypatch.setattr(agent, "_printer_enum_failed", False)
        with caplog.at_level(logging.INFO, logger="wms_print_agent"):
            assert agent.send_heartbeat(self._cfg()) is True
            assert agent.send_heartbeat(self._cfg()) is True  # 连续失败第二轮
        # 两次心跳 payload 的 printers 都是 None（不上报空列表，服务端据此保留状态）
        assert len(sent) == 2 and all(p["printers"] is None for p in sent)
        warns = [r for r in caplog.records
                 if r.levelname == "WARNING" and "枚举失败" in r.getMessage()]
        assert len(warns) == 1  # 节流：进入失败只打一条
        assert agent._printer_enum_failed is True

    def test_recovery_sends_list_and_logs(self, monkeypatch, caplog):
        import logging
        monkeypatch.setattr(agent, "_printer_enum_failed", True)  # 之前处于失败态
        plist = [{"system_name": "HP", "status": "ready", "is_default": True}]
        monkeypatch.setattr(agent, "enumerate_printers", lambda: plist)
        sent = []
        monkeypatch.setattr(agent, "api_call",
                            lambda *a: sent.append(a[3]) or
                            (200, {"status": "success", "data": {"printers_online": 1}}))
        with caplog.at_level(logging.INFO, logger="wms_print_agent"):
            assert agent.send_heartbeat(self._cfg()) is True
        assert sent[0]["printers"] == plist  # 恢复后正常上报列表
        assert agent._printer_enum_failed is False
        recov = [r for r in caplog.records if "已恢复" in r.getMessage()]
        assert len(recov) == 1


class TestDefaultPrinter:
    """BUG-2026-08-19-007：Win7 PS 2.0 定向打印后默认打印机永不恢复。"""

    def test_get_default_printer_falls_back_to_wmi(self, monkeypatch):
        """Get-CimInstance 在 PS 2.0 不存在（空串），必须回退 Get-WmiObject。"""
        calls = []

        def fake_run(command):
            calls.append(command)
            if "Get-CimInstance" in command:
                return ""
            return "HP LaserJet 1020"

        monkeypatch.setattr(agent, "_run_powershell", fake_run)
        assert agent.get_default_printer() == "HP LaserJet 1020"
        assert any("Get-WmiObject" in c for c in calls)

    def test_set_default_printer_success_marker(self, monkeypatch):
        """SetDefaultPrinter 成功时 PowerShell 无输出（空串），命令必须显式
        回写成功标记，否则 bool('') 误判为失败、原默认打印机永不恢复。"""
        seen = {}

        def fake_run(command):
            seen["cmd"] = command
            return "OK"

        monkeypatch.setattr(agent, "_run_powershell", fake_run)
        assert agent.set_default_printer("HP LaserJet 1020") is True
        assert "$?" in seen["cmd"]  # 命令含成功判定

    def test_set_default_printer_failure_returns_false(self, monkeypatch):
        monkeypatch.setattr(agent, "_run_powershell", lambda cmd: "")
        assert agent.set_default_printer("HP") is False

    def test_set_default_printer_escapes_single_quotes(self, monkeypatch):
        """打印机名含单引号（如 O'Brien）时必须转义为 PS 单引号字符串内的
        两个单引号，否则命令被截断/注入。"""
        seen = {}

        def fake_run(command):
            seen["cmd"] = command
            return "OK"

        monkeypatch.setattr(agent, "_run_powershell", fake_run)
        assert agent.set_default_printer("O'Brien 1100") is True
        assert "O''Brien 1100" in seen["cmd"]


class TestLoadConfig:
    def test_missing_server_token_exits(self, tmp_path, monkeypatch):
        monkeypatch.delenv("WMS_AGENT_SERVER_URL", raising=False)
        monkeypatch.delenv("WMS_AGENT_TOKEN", raising=False)
        with pytest.raises(SystemExit):
            agent.load_config(_args(config=str(tmp_path / "none.json")))

    def test_precedence_args_over_env_over_file(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "agent_config.json"
        cfg_file.write_text(json.dumps({
            "server_url": "http://file:5000/",
            "token": "tok-file",
            "poll_interval": 9,
        }), encoding="utf-8")
        monkeypatch.setenv("WMS_AGENT_SERVER_URL", "http://env:5000")
        monkeypatch.setenv("WMS_AGENT_TOKEN", "tok-env")
        # 环境变量覆盖文件，参数覆盖环境变量
        cfg = agent.load_config(_args(config=str(cfg_file)))
        assert cfg["server_url"] == "http://env:5000"
        assert cfg["token"] == "tok-env"
        assert cfg["poll_interval"] == 9  # 文件提供，未被环境/参数覆盖
        cfg = agent.load_config(_args(config=str(cfg_file),
                                      server_url="http://arg:5000", token="tok-arg",
                                      poll_interval=5, directed_printer=False))
        assert cfg["server_url"] == "http://arg:5000"
        assert cfg["token"] == "tok-arg"
        assert cfg["poll_interval"] == 5
        assert cfg["directed_printer"] is False

    def test_defaults(self, tmp_path, monkeypatch):
        monkeypatch.delenv("WMS_AGENT_SERVER_URL", raising=False)
        monkeypatch.delenv("WMS_AGENT_TOKEN", raising=False)
        cfg = agent.load_config(_args(config=str(tmp_path / "none.json"),
                                      server_url="http://x:1", token="t"))
        assert cfg["heartbeat_interval"] == agent.DEFAULT_HEARTBEAT_INTERVAL
        assert cfg["directed_printer"] is True
