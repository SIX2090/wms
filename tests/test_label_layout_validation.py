# -*- coding: utf-8 -*-
"""BUG-2026-10-17-011：标签模板 layout 写入侧校验（存储型 XSS 的根因之一）。

模板设计页已改为 tojson 渲染；本用例锁住写入侧：只接受合法 JSON 对象，
非法 JSON / 标量必须拒绝，列表旧格式包成 cells。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
for path in (str(APP_DIR), str(APP_DIR / 'routes')):
    if path not in sys.path:
        sys.path.insert(0, path)

import label_barcode  # noqa: E402


def test_accepts_json_object_string():
    assert label_barcode._parse_label_layout('{"cells": []}') == {'cells': []}


def test_empty_and_none_become_empty_object():
    assert label_barcode._parse_label_layout('') == {}
    assert label_barcode._parse_label_layout(None) == {}


def test_dict_passthrough_and_list_wrapped():
    data = {'0-0': {'field': 'name'}}
    assert label_barcode._parse_label_layout(data) == data
    assert label_barcode._parse_label_layout([{'row': 0}]) == {'cells': [{'row': 0}]}


@pytest.mark.parametrize('raw', ['not-json', '{"a": ', '42', '"text"', 'true'])
def test_rejects_invalid_or_scalar_json(raw):
    with pytest.raises(ValueError):
        label_barcode._parse_label_layout(raw)


def test_dangerous_string_is_kept_as_data_not_html():
    raw = json.dumps({'label': '</script><script>alert(1)</script>'})
    parsed = label_barcode._parse_label_layout(raw)
    assert parsed['label'] == '</script><script>alert(1)</script>'
    # 写入侧只保证是合法 JSON；输出侧由模板 tojson 转义（见 test_label_layout_script_encoding）
