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
    def test_non_windows_returns_empty(self):
        if os.name == "nt":
            pytest.skip("仅验证非 Windows 环境的空列表行为")
        assert agent.enumerate_printers() == []


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
