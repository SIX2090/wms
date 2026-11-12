#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用「关键词匹配选择」候选数据源（AI-WMS-FILTER-001）。

为全系统筛选输入框提供统一候选，供前端 quick-select 组件消费：

    GET /api/options/<entity>?kw=关键词&limit=50&offset=0

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
- BUG-2026-11-12-001（新建物料下拉不显示）：候选池 TTL 内不回源，新建/删除/
  停启用/导入/合并物料后，全系统筛选下拉最长 300 秒看不到变化。现缓存命中时
  先做一次「表指纹」探测（行数 + 最大 id + 可入池行数，亚毫秒级），签名变化
  立即重建候选池——覆盖一切改变行数的写入路径，无需逐写入点手工失效；
  「不改行数的字段编辑」（改名称/规格/品牌）探测不到，由 routes/material.py
  的物料编辑路由显式调用 invalidate_options_pool() 补位。
- 拼音计算按文本记忆化（lru_cache）：候选池重建只回源数据库，拼音零重算，
  签名触发重建的响应仍在毫秒级，下拉体感不受影响。
- 数据量 > _SQL_THRESHOLD 时退化为 SQL LIKE 预过滤（保证大数据量不拖垮内存）
- pypinyin 缺失时自动降级为纯子串匹配
"""
from __future__ import annotations

import time
from functools import lru_cache
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
    # F2.16：BOM 搜索式下拉（领料单关联BOM），字段 bom_no + product_name
    'bom':        ('BOM',              'bom_no',      'product_name', ()),
    'bom_active': ('BOM',              'bom_no',      'product_name', ('product_code', 'version')),
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


@lru_cache(maxsize=100000)
def _py_keys(text):
    """返回 (全拼, 首字母)。如 电缆 -> ('dianlan', 'dl')。

    BUG-2026-11-12-001：按文本记忆化——候选池因签名变化/ TTL 到期重建时
    只回源数据库，拼音不重算（物料名/规格等文本稳定，缓存命中率极高），
    重建耗时从「全量拼音重算」降到「一次全表 SELECT + 字典查找」，毫秒级。
    """
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
    # 2026-09-25：物料排除停用。本函数是 16 处模板 quick-select 的统一候选源，
    # 不停在这里过滤，停用物料会继续出现在库存查询/列表的物料下拉里。
    _q = M.query
    if entity == 'bom_active':
        _q = _q.filter(M.status == 'active')
    if entity == 'material' and hasattr(M, 'status'):
        from db import db as _db
        _q = _q.filter(_db.or_(M.status == 'active',
                               M.status.is_(None), M.status == ''))
    rows = _q.all()
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
    _q = M.query.filter(db.or_(*conds))
    if entity == 'bom_active':
        _q = _q.filter(M.status == 'active')
    # 2026-09-25：同上，大数据量退化路径也要排除停用物料
    if entity == 'material' and hasattr(M, 'status'):
        _q = _q.filter(db.or_(M.status == 'active',
                              M.status.is_(None), M.status == ''))
    # 分批读取匹配行；不能把一批的大小当成候选全集上限。
    rows = _q.order_by(M.id).yield_per(_MAX_SQL_ROWS)
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


def _entity_pool_signature(key):
    """候选池底层主数据表的廉价指纹：(总行数, 最大id, 可入池行数)。

    BUG-2026-11-12-001（新建物料下拉不显示）：候选池命中 300 秒 TTL 时
    不再盲目信任缓存，先用本指纹做一次亚毫秒级探测——主数据有任何
    「改变行数/最大id/可入池行数」的写入（新建/删除/停启用/导入/合并/
    批量导入），签名即变化、候选池立即重建。这样无需在每个写入点手工
    失效，天然覆盖 PC 新增、物料导入、批量导入、手机端等一切入口，
    不会像逐点失效那样漏掉新增入口（R6 同根因漂移）。

    局限（有意取舍）：不改行数的字段编辑（改名称/规格/品牌）探测不到，
    由 routes/material.py 的物料编辑路由显式调用 invalidate_options_pool()
    补位。探测抛异常时返回 None，调用方按「未变化」处理，绝不让下拉 500。
    """
    if key not in ENTITY_CONFIG:
        return None
    M = _model(ENTITY_CONFIG[key][0])
    if M is None:
        return None
    try:
        from db import db as _db
        total = M.query.count()
        max_id = _db.session.query(_db.func.max(M.id)).scalar() or 0
        eligible = None
        # 物料/BOM 候选池带 status 过滤（见 _build_entity_pool），停用/启用
        # 不改变总行数与最大 id，必须用「可入池行数」这一维才能感知。
        if key == 'material' and hasattr(M, 'status'):
            eligible = M.query.filter(_db.or_(M.status == 'active',
                                              M.status.is_(None),
                                              M.status == '')).count()
        elif key == 'bom_active':
            eligible = M.query.filter(M.status == 'active').count()
        return (total, max_id, eligible)
    except Exception:
        current_app.logger.warning('[options] 表指纹探测失败 entity=%s，沿用缓存', key,
                                   exc_info=True)
        return None


def invalidate_options_pool(entity=None):
    """显式失效候选池缓存（BUG-2026-11-12-001 配套）。

    签名探测已覆盖一切改变行数的写入；本函数只用于补位「探测感知不到」
    的场景——目前唯一已知是物料编辑改 code/name/spec/brand 文本（行数与
    id 不变）。entity 传 None 清空全部实体（主数据极少变更，重建成本由
    _py_keys 记忆化承担，毫秒级），传实体名只清该实体。
    """
    with _POOL_LOCK:
        if entity:
            _POOL_CACHE.pop(entity, None)
        else:
            _POOL_CACHE.clear()


def _get_pool(key, kw):
    """取候选池：优先内存缓存，超阈值则走 SQL。"""
    now = time.time()
    with _POOL_LOCK:
        cached = _POOL_CACHE.get(key)
    if cached and now - cached[0] < _POOL_TTL:
        pool, sig = cached[1], cached[2]
        # BUG-2026-11-12-001：TTL 未到也先做表指纹探测，主数据变了立即重建；
        # 纯文本候选（TEXT_SOURCES）签名恒 None，保持纯 TTL 行为。
        # 探测结果为 None（探测失败）按「未变化」处理：新鲜度优化绝不把
        # 下拉打成 500 或强制慢路径，回退旧缓存（最多旧 300 秒）。
        try:
            current = _entity_pool_signature(key)
        except Exception:
            current = None
        if sig is None or current is None or current == sig:
            return pool, True
        with _POOL_LOCK:
            # 只清掉「探测时的同一份缓存」：若并发请求已先一步重建，让位。
            if _POOL_CACHE.get(key) is cached:
                _POOL_CACHE.pop(key, None)

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

    sig = _entity_pool_signature(key) if key in ENTITY_CONFIG else None
    with _POOL_LOCK:
        _POOL_CACHE[key] = (now, pool, sig)
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
    # F2.5 / S6：鉴权改为**请求期解析**。原因：本 register 在 app.py 中的调用点
    # （约 3489 行）早于 web_or_api_required 的定义（约 7038 行），注册期必然取不到
    # 该装饰器；此前代码因此在注册期降级为「不鉴权」→ /api/options/* 长期匿名放行
    # （这正是 S6 的实质）。改为请求期解析后：匿名请求被拒（401），解析失败则
    # fail-close（抛出即 500），绝不降级为匿名放行。
    def _decorate(fn):
        from functools import wraps

        # no-test:reason=装饰器包装函数，由 endpoint 鉴权测试覆盖
        @wraps(fn)
        def _guarded(*args, **kwargs):
            from app import web_or_api_required as _real
            return _real(fn)(*args, **kwargs)

        return _guarded

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
        try:
            offset = max(0, int(request.values.get('offset') or 0))
        except (TypeError, ValueError):
            offset = 0

        low = kw.lower()
        try:
            pool, cached = _get_pool(entity, kw)
            scored = []
            for item in pool:
                s = _score(item, low)
                if s:
                    scored.append((s, item))
            scored.sort(key=lambda x: (-x[0], len(x[1]['label']),
                                       x[1]['code'], str(x[1]['id'])))
            data = []
            for _s, item in scored[offset:offset + limit]:
                data.append({k: v for k, v in item.items() if not k.startswith('_')})
            return jsonify({
                'status': 'success',
                'data': data,
                'total': len(scored),
                'offset': offset,
                'limit': limit,
                'has_more': offset + len(data) < len(scored),
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
