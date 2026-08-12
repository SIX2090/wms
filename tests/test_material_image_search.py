# -*- coding: utf-8 -*-
"""物料网上找图功能测试：搜索词聚焦 name+spec、百度图片 JSON 解析、百度首选+Bing fallback。

覆盖三项改动：
  1. _material_image_search_terms 只取 name+spec+brand，不再追加 "工业品 标准件 产品图片"
  2. _extract_baidu_image_candidates 正确解析百度 acjson JSON
  3. _search_material_images_online 百度首选、Bing fallback
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    _material_image_search_terms,
    _extract_baidu_image_candidates,
    _extract_bing_image_candidates,
    _search_material_images_online,
    Material,
    MaterialCategory,
    Unit,
    db,
)


# ─── 搜索词构造 ───

class _FakeMaterial:
    """轻量 mock，避免完整 ORM 开销。"""
    def __init__(self, name='', spec='', brand='', purpose='', category=None):
        self.name = name
        self.spec = spec
        self.brand = brand
        self.purpose = purpose
        self.category = category


class _FakeCategory:
    def __init__(self, name):
        self.name = name


def test_search_terms_name_plus_spec():
    """搜索词以 name + spec 为主。"""
    m = _FakeMaterial(name='6204轴承', spec='6204', brand='SKF')
    terms = _material_image_search_terms(m)
    assert '6204轴承' in terms
    assert '6204' in terms
    assert 'SKF' in terms


def test_search_terms_no_industrial_suffix():
    """不再追加 '工业品 标准件 产品图片' 噪声后缀。"""
    m = _FakeMaterial(name='M8螺母', spec='M8')
    terms = _material_image_search_terms(m)
    assert '工业品' not in terms
    assert '产品图片' not in terms
    assert '标准件' not in terms


def test_search_terms_no_purpose_category():
    """不再包含 purpose 和 category（聚焦 name+spec+brand）。"""
    m = _FakeMaterial(
        name='电阻', spec='1KΩ', brand='',
        purpose='电子元件', category=_FakeCategory('电子耗材'),
    )
    terms = _material_image_search_terms(m)
    assert '电子元件' not in terms
    assert '电子耗材' not in terms


def test_search_terms_empty_material():
    """空物料返回空字符串。"""
    m = _FakeMaterial()
    assert _material_image_search_terms(m) == ''


def test_search_terms_dedup():
    """重复 token 去重。"""
    m = _FakeMaterial(name='轴承 6204', spec='6204 轴承', brand='')
    terms = _material_image_search_terms(m)
    tokens = terms.split()
    # "6204" 和 "轴承" 各只出现一次
    assert tokens.count('6204') == 1
    assert tokens.count('轴承') == 1


# ─── 百度图片 JSON 解析 ───

def test_extract_baidu_basic():
    """正常 JSON → 提取 middleURL/thumbURL/title。"""
    data = {
        "data": [
            {
                "thumbURL": "https://img0.baidu.com/thumb.jpg",
                "middleURL": "https://img0.baidu.com/middle.jpg",
                "objURL": "ipprf_z2C$q_encoded",
                "fromURL": "ippr_z2C$q_encoded",
                "fromPageTitle": "6204<strong>轴承</strong>深沟球",
            },
            {
                "thumbURL": "https://img1.baidu.com/thumb2.jpg",
                "middleURL": "https://img1.baidu.com/middle2.jpg",
                "fromPageTitle": "不锈钢螺母",
            },
        ]
    }
    candidates = _extract_baidu_image_candidates(data, limit=12)
    assert len(candidates) == 2
    assert candidates[0]['image_url'] == 'https://img0.baidu.com/middle.jpg'
    assert candidates[0]['thumb_url'] == 'https://img0.baidu.com/thumb.jpg'
    # HTML 标签被清理
    assert '<strong>' not in candidates[0]['title']
    assert '6204' in candidates[0]['title']
    assert '轴承' in candidates[0]['title']


def test_extract_baidu_skip_invalid():
    """跳过无 thumbURL/middleURL 或非 http 的条目。"""
    data = {
        "data": [
            {"thumbURL": "", "middleURL": ""},  # 空 URL 跳过
            {"thumbURL": "ftp://bad", "middleURL": "ftp://bad"},  # 非 http 跳过
            {"thumbURL": "https://img.baidu.com/ok.jpg"},  # 有效
            "not_a_dict",  # 非字典跳过
        ]
    }
    candidates = _extract_baidu_image_candidates(data, limit=12)
    assert len(candidates) == 1
    assert candidates[0]['image_url'] == 'https://img.baidu.com/ok.jpg'


def test_extract_baidu_dedup():
    """重复 middleURL 去重。"""
    data = {
        "data": [
            {"thumbURL": "https://a.com/t.jpg", "middleURL": "https://a.com/m.jpg"},
            {"thumbURL": "https://b.com/t.jpg", "middleURL": "https://a.com/m.jpg"},  # 重复
        ]
    }
    candidates = _extract_baidu_image_candidates(data, limit=12)
    assert len(candidates) == 1


def test_extract_baidu_limit():
    """limit 截断。"""
    data = {
        "data": [{"thumbURL": f"https://img{i}.baidu.com/t.jpg", "middleURL": f"https://img{i}.baidu.com/m.jpg"} for i in range(20)]
    }
    candidates = _extract_baidu_image_candidates(data, limit=5)
    assert len(candidates) == 5


def test_extract_baidu_source_url_filter():
    """fromURL 非 http 时 source_url 为空。"""
    data = {
        "data": [
            {
                "thumbURL": "https://img.baidu.com/t.jpg",
                "middleURL": "https://img.baidu.com/m.jpg",
                "fromURL": "ippr_z2C$q_encoded",
            }
        ]
    }
    candidates = _extract_baidu_image_candidates(data, limit=12)
    assert candidates[0]['source_url'] == ''


# ─── _search_material_images_online 集成（mock requests） ───

def test_search_baidu_first_success():
    """百度有结果时直接返回，不请求 Bing。"""
    m = _FakeMaterial(name='6204轴承', spec='6204')

    baidu_resp = MagicMock()
    baidu_resp.json.return_value = {
        "data": [{"thumbURL": "https://img.baidu.com/t.jpg", "middleURL": "https://img.baidu.com/m.jpg"}]
    }
    baidu_resp.raise_for_status = MagicMock()

    with patch('app.requests.get', return_value=baidu_resp) as mock_get:
        candidates, query = _search_material_images_online(m)

    assert len(candidates) == 1
    assert '6204轴承' in query
    # 只被调用一次（百度），没有 fallback 到 Bing
    assert mock_get.call_count == 1
    assert 'image.baidu.com' in mock_get.call_args[0][0]


def test_search_baidu_fail_fallback_bing():
    """百度异常时 fallback 到 Bing。"""
    m = _FakeMaterial(name='M8螺母', spec='M8')

    bing_html = '''
    <div m="{&quot;murl&quot;:&quot;https://example.com/bing_img.jpg&quot;,&quot;turl&quot;:&quot;https://bingthumb.com/t.jpg&quot;,&quot;t&quot;:&quot;M8螺母&quot;}"></div>
    '''
    bing_resp = MagicMock()
    bing_resp.text = bing_html
    bing_resp.raise_for_status = MagicMock()

    with patch('app.requests.get', side_effect=[Exception("baidu timeout"), bing_resp]) as mock_get:
        candidates, query = _search_material_images_online(m)

    assert len(candidates) >= 1
    assert candidates[0]['image_url'] == 'https://example.com/bing_img.jpg'
    assert mock_get.call_count == 2
    # 第一次百度，第二次 Bing
    assert 'image.baidu.com' in mock_get.call_args_list[0][0][0]
    assert 'bing.com' in mock_get.call_args_list[1][0][0]


def test_search_baidu_empty_fallback_bing():
    """百度返回空结果时 fallback 到 Bing。"""
    m = _FakeMaterial(name='密封圈', spec='O型')

    baidu_resp = MagicMock()
    baidu_resp.json.return_value = {"data": []}
    baidu_resp.raise_for_status = MagicMock()

    bing_resp = MagicMock()
    bing_resp.text = ''
    bing_resp.raise_for_status = MagicMock()

    with patch('app.requests.get', side_effect=[baidu_resp, bing_resp]) as mock_get:
        candidates, query = _search_material_images_online(m)

    # Bing 也没结果 → 空列表
    assert candidates == []
    assert '密封圈' in query
    assert mock_get.call_count == 2


def test_search_both_fail_returns_empty():
    """百度和 Bing 都失败时返回空列表，不抛异常。"""
    m = _FakeMaterial(name='垫片', spec='Φ10')

    with patch('app.requests.get', side_effect=Exception("network error")):
        candidates, query = _search_material_images_online(m)

    assert candidates == []
    assert '垫片' in query
