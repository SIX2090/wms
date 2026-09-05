#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用「关键词匹配选择」候选数据源（AI-WMS-FILTER-001）。

为全系统筛选输入框提供统一候选，供前端 quick-select 组件消费：

    GET /api/options/<entity>?kw=关键词&limit=50

统一返回：
    {"status":"success","data":[{"id":..,"code":..,"name":..,"sub":..,"label":..}]}

物料（material）额外下发独立字段 spec / brand（AI-WMS-FILTER-005），
供前端 quick-select 富展示「编码 + 名称 + 规格 + 品牌」；
sub 仍保留（规格+品牌拼接文本），向后兼容。

匹配能力（按优先级）：
- 中文/编码子串匹配（编码、名称、规格、品牌等）
- 拼音全拼匹配（dianlan -> 电缆）
- 拼音首字母匹配（dl -> 电缆）
- 完全一致 > 前缀匹配 > 包含匹配 排序

性能策略：
- 候选池内存缓存（TTL 300s），拼音索引首次构建后复用
- 数据量 > _SQL_THRESHOLD 时退化为 SQL LIKE 预过滤（保证大数据量不拖垮内存）
- pypinyin 缺失时自动降级为纯子串匹配
"""
from __future__ import annotations

import time
from threading import Lock

from flask import current_app, jsonify, request

try:
    from pypinyin import lazy_pinyin, Style
    _HAS_PINYIN = True
except Exception:  # pragma: no cover - 降级路径
    _HAS_PINYIN = False


# entity -> (模型名, 编码字段, 名称字段, 参与匹配的额外字段)
ENTITY_CONFIG = {
    'material':   ('Material',         'code', 'name', ('spec', 'brand')),
    'supplier':   ('Supplier',         'code', 'name', ()),
    'customer':   ('Customer',         'code', 'name', ()),
    'warehouse':  ('Warehouse',        'code', 'name', ()),
    'employee':   ('Employee',         'code', 'name', ()),
    'department': ('Department',       'code', 'name', ()),
    'unit':       ('Unit',             'code', 'name', ()),
    'category':   ('MaterialCategory', 'code', 'name', ()),
    'contract':   ('Contract',         'contract_no', 'project_name', ()),
}

# 纯文本候选：从多张表的历史值去重提取（无 id）
TEXT_SOURCES = {
    'project': (
        ('Contract', 'project_name'),
        ('InOrder', 'project_name'),
        ('OutOrder', 'project_name'),
        ('PurchaseOrder', 'project_name'),
        ('SalesOrder', 'project_name'),
    ),
    'contract_no': (
        ('Contract', 'contract_no'),
        ('InOrder', 'contract_no'),
        ('OutOrder', 'contract_no'),
        ('PurchaseOrder', 'contract_no'),
        ('SalesOrder', 'contract_no'),
    ),
}

_POOL_CACHE: dict = {}
_POOL_LOCK = Lock()
_POOL_TTL = 300.0
_SQL_THRESHOLD = 5000   # 超过此条数改用 SQL 预过滤
_MAX_SQL_ROWS = 500


def _model(name):
    """延迟导入 app.py 中定义的模型，避免循环导入。"""
    try:
        import app as _app_mod
        return getattr(_app_mod, name, None)
    except Exception:
        return None


def _py_keys(text):
    """返回 (全拼, 首字母)。如 电缆 -> ('dianlan', 'dl')。"""
    if not text or not _HAS_PINYIN:
        return '', ''
    try:
        full = ''.join(lazy_pinyin(text, style=Style.NORMAL))
        init = ''.join(lazy_pinyin(text, style=Style.FIRST_LETTER))
        return full, init
    except Exception:
        return '', ''


def _mk_item(id_, code, name, sub, label):
    code = str(code or '').strip()
    name = str(name or '').strip()
    sub = str(sub or '').strip()
    text = ' '.join(x for x in (code, name, sub) if x)
    full, init = _py_keys(text)
    return {
        'id': id_,
        'code': code,
        'name': name,
        'sub': sub,
        'label': label if label is not None else (code or name),
        '_t': text.lower(),
        '_f': full.lower(),
        '_i': init.lower(),
    }


def _build_entity_pool(entity):
    cfg = ENTITY_CONFIG.get(entity)
    if not cfg:
        return []
    mname, cfield, nfield, extras = cfg
    M = _model(mname)
    if M is None:
        return []
    rows = M.query.all()
    pool = []
    for r in rows:
        extras_text = ' '.join(
            str(getattr(r, f) or '').strip() for f in extras if getattr(r, f, None)
        )
        item = _mk_item(
            getattr(r, 'id', None),
            getattr(r, cfield, ''),
            getattr(r, nfield, ''),
            extras_text,
            None,
        )
        # AI-WMS-FILTER-005：extras 字段（物料 spec/brand）独立下发，
        # 供前端富展示「编码+名称+规格+品牌」，不再只依赖 sub 拼接文本。
        for f in extras:
            item[f] = str(getattr(r, f) or '').strip()
        pool.append(item)
    return pool


def _build_text_pool(key):
    from db import db

    pool, seen = [], set()
    for mname, field in TEXT_SOURCES.get(key, ()):
        M = _model(mname)
        if M is None:
            continue
        col = getattr(M, field, None)
        if col is None:
            continue
        try:
            rows = db.session.query(col).distinct().all()
        except Exception:
            db.session.rollback()
            continue
        for (v,) in rows:
            v = str(v or '').strip()
            if not v or v in seen:
                continue
            seen.add(v)
            pool.append(_mk_item(None, v, v, '', v))
    return pool


def _sql_like_pool(entity, kw):
    """大数据量退化路径：用 SQL LIKE 先过滤。"""
    from db import db

    cfg = ENTITY_CONFIG.get(entity)
    if not cfg:
        return []
    mname, cfield, nfield, extras = cfg
    M = _model(mname)
    if M is None:
        return []
    like = '%{}%'.format(kw)
    conds = [getattr(M, f).like(like) for f in (cfield, nfield) + tuple(extras)
             if getattr(M, f, None) is not None]
    if not conds:
        return []
    rows = M.query.filter(db.or_(*conds)).limit(_MAX_SQL_ROWS).all()
    # AI-WMS-FILTER-005：sub 必须带 extras 拼接文本——此前 sub='' 导致
    # 按规格/品牌关键词命中的行在 _score 阶段被误杀（_t 不含 extras），
    # 大数据量（>5000）时按规格/品牌搜索永远空结果；同时独立下发 extras 字段。
    items = []
    for r in rows:
        extras_text = ' '.join(
            str(getattr(r, f) or '').strip() for f in extras if getattr(r, f, None)
        )
        item = _mk_item(getattr(r, 'id', None), getattr(r, cfield, ''),
                        getattr(r, nfield, ''), extras_text, None)
        for f in extras:
            item[f] = str(getattr(r, f) or '').strip()
        items.append(item)
    return items


def _get_pool(key, kw):
    """取候选池：优先内存缓存，超阈值则走 SQL。"""
    now = time.time()
    with _POOL_LOCK:
        cached = _POOL_CACHE.get(key)
        if cached and now - cached[0] < _POOL_TTL:
            return cached[1], True

    if key in ENTITY_CONFIG:
        M = _model(ENTITY_CONFIG[key][0])
        try:
            total = M.query.count() if M is not None else 0
        except Exception:
            total = 0
        if total > _SQL_THRESHOLD and kw:
            return _sql_like_pool(key, kw), False
        pool = _build_entity_pool(key)
    else:
        pool = _build_text_pool(key)

    with _POOL_LOCK:
        _POOL_CACHE[key] = (now, pool)
    return pool, False


def _score(item, low):
    """匹配打分，0 表示不匹配。"""
    if not low:
        return 1
    if low in item['_t']:
        code = (item['code'] or '').lower()
        name = (item['name'] or '').lower()
        if code == low or name == low:
            return 100
        if code.startswith(low) or name.startswith(low):
            return 85
        return 70
    if item['_f'] and low in item['_f']:
        return 60 if item['_f'].startswith(low) else 50
    if item['_i'] and low in item['_i']:
        return 45 if item['_i'].startswith(low) else 40
    return 0


def register_options_routes(app):
    """在 app 上注册通用候选接口。endpoint: api_options"""
    # 认证：Web 会话或 API Token 均可（与系统其它 API 一致）。
    # 延迟导入避免循环依赖；取不到时降级为不鉴权（内网部署场景）。
    try:
        from app import web_or_api_required as _auth_required
    except Exception:
        _auth_required = None

    def _decorate(fn):
        return _auth_required(fn) if _auth_required else fn

    @app.route('/api/options/<entity>', methods=['GET'])
    @_decorate
    def api_options(entity):
        entity = (entity or '').strip().lower()
        if entity not in ENTITY_CONFIG and entity not in TEXT_SOURCES:
            return jsonify({'status': 'error', 'message': '未知实体: %s' % entity,
                            'data': []}), 404

        kw = (request.values.get('kw')
              or request.values.get('keyword')
              or request.values.get('q')
              or '').strip()
        try:
            limit = int(request.values.get('limit') or 50)
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))

        low = kw.lower()
        try:
            pool, cached = _get_pool(entity, kw)
            scored = []
            for item in pool:
                s = _score(item, low)
                if s:
                    scored.append((s, item))
            scored.sort(key=lambda x: (-x[0], len(x[1]['label'])))
            data = []
            for _s, item in scored[:limit]:
                data.append({k: v for k, v in item.items() if not k.startswith('_')})
            return jsonify({
                'status': 'success',
                'data': data,
                'total': len(scored),
                'cached': cached,
                'pinyin': _HAS_PINYIN,
            })
        except Exception as exc:
            current_app.logger.exception('[options] 候选查询失败 entity=%s kw=%s',
                                         entity, kw)
            return jsonify({'status': 'error', 'message': str(exc), 'data': []}), 500

    # 与 /mobile/api/ 一致：API 调用不携带 CSRF token，需豁免
    try:
        from app import csrf as _csrf
        _csrf.exempt(api_options)
    except Exception:
        pass

    return app
