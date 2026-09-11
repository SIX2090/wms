#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 原生/移动端 API + 通用数据查询（native_api）域路由。
#
# 批量拆分模式：与销售（sales）、库存调整（adjustment）等域一致，采用
# 「register_native_api_routes(app)」直接在 app 上注册路由，endpoint 名保持不变
# （如 api_csrf_refresh、native_api_login、native_api_inbound、mobile_api_dashboard、
# api_categories 等），与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / db），不导入 app，避免循环导入。
# - app.py 内部定义（csrf、api_role_required、mobile_api_idempotent、web_or_api_required
#   等装饰器，User、ApiToken、InOrder、InOrderItem、OutOrder、OutOrderItem、Material、
#   MaterialCategory、Unit、Supplier、Customer、InventoryCheckScan、
#   InventoryCheckScanItem 等模型，以及 api_json_error / api_json_success /
#   api_json_error / get_request_ip / get_bearer_user / add_login_log / parse_api_lines /
#   parse_float_value / generate_order_no / round_to_2_decimals / normalize_stock_quantity /
#   add_stock / deduct_stock / update_location_inventory / check_stock_sufficient /
#   purchase_in_order_requires_order / location_management_enabled /
#   location_required_on_save / allow_negative_stock / inventory_alert_enabled /
#   _create_adjustment_drafts_from_check_scan / _mobile_paginate / _in_order_payload /
#   _in_order_detail_payload / _out_order_payload / _out_order_detail_payload /
#   serialize_unit / serialize_supplier / serialize_customer / MOBILE_API_PAGE_SIZE_DEFAULT /
#   MOBILE_API_PAGE_SIZE_MAX 等）在各路由函数内延迟导入（请求期才执行），
#   避免 app.py 模块加载期触发循环导入。
# - 装饰器 csrf / api_role_required / mobile_api_idempotent / web_or_api_required 需在
#   路由函数定义期可用，故在 register_native_api_routes(app) 函数内延迟导入。
# - 日志复用 register_native_api_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

import re

from flask import jsonify, request

from db import db


def _ensure_login_schema():
    """确保登录所需的关键表和列存在（WMS_NO_DB_TOUCH=1 场景下兜底）。

    当 WMS_NO_DB_TOUCH=1 时，auto_migrate_database() 和 db.create_all() 均被跳过，
    老数据库可能缺少 user 表的登录安全列、api_token 表或 login_log 表，
    导致 /api/login 抛 OperationalError → 500 → nginx 502。

    本函数在首次登录请求时补建缺失的表/列，确保登录功能正常。
    """
    from sqlalchemy import inspect as sa_inspect, text
    from app import db as _db
    try:
        inspector = sa_inspect(_db.engine)
        # 1. 确保 api_token 表存在
        if not inspector.has_table('api_token'):
            from app import ApiToken
            ApiToken.__table__.create(_db.engine, checkfirst=True)
        # 2. 确保 login_log 表存在
        if not inspector.has_table('login_log'):
            from app import LoginLog
            LoginLog.__table__.create(_db.engine, checkfirst=True)
        # 3. 确保 user 表缺失的列存在
        if inspector.has_table('user'):
            user_cols = {col['name'] for col in inspector.get_columns('user')}
            missing = {
                'login_failed_count': 'ALTER TABLE "user" ADD COLUMN login_failed_count INTEGER DEFAULT 0',
                'locked_until': 'ALTER TABLE "user" ADD COLUMN locked_until DATETIME',
                'last_login_at': 'ALTER TABLE "user" ADD COLUMN last_login_at DATETIME',
                'last_login_ip': 'ALTER TABLE "user" ADD COLUMN last_login_ip VARCHAR(50)',
                'must_change_password': 'ALTER TABLE "user" ADD COLUMN must_change_password BOOLEAN DEFAULT 0',
                'login_lock_ip': 'ALTER TABLE "user" ADD COLUMN login_lock_ip VARCHAR(50)',
                'login_ip_failed_count': 'ALTER TABLE "user" ADD COLUMN login_ip_failed_count INTEGER DEFAULT 0',
                'login_ip_locked_until': 'ALTER TABLE "user" ADD COLUMN login_ip_locked_until DATETIME',
                'email': 'ALTER TABLE "user" ADD COLUMN email VARCHAR(200)',
                'phone': 'ALTER TABLE "user" ADD COLUMN phone VARCHAR(30)',
                'bio': 'ALTER TABLE "user" ADD COLUMN bio VARCHAR(500)',
            }
            with _db.engine.connect() as conn:
                for col_name, ddl in missing.items():
                    if col_name not in user_cols:
                        conn.execute(text(ddl))
                conn.commit()
        # 4. 确保 api_token 表有 last_used_at 列
        if inspector.has_table('api_token'):
            token_cols = {col['name'] for col in inspector.get_columns('api_token')}
            if 'last_used_at' not in token_cols:
                with _db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE api_token ADD COLUMN last_used_at DATETIME'))
                    conn.commit()
        # 5. 确保 login_log 表有 fail_reason 列
        if inspector.has_table('login_log'):
            log_cols = {col['name'] for col in inspector.get_columns('login_log')}
            if 'fail_reason' not in log_cols:
                with _db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE login_log ADD COLUMN fail_reason VARCHAR(200)'))
                    conn.commit()
        return True
    except Exception:
        return False


def _resolve_material_unit(unit_name):
    """解析单位：优先按 name/code 精确匹配，其次忽略大小写，最后回退默认单位。"""
    from sqlalchemy import func
    from app import Unit
    name = (unit_name or '').strip()
    if name:
        unit = Unit.query.filter(
            db.or_(Unit.name == name, Unit.code == name)
        ).first()
        if not unit:
            unit = Unit.query.filter(
                func.lower(Unit.name) == func.lower(name)
            ).first()
        if unit:
            return unit
    default = Unit.query.filter_by(name='个').first()
    return default or Unit.query.first()


def _find_material_by_name_spec(name, spec=None):
    """按名称+规格查既有建档物料，避免自动建档产生重复。"""
    from sqlalchemy import func
    from app import Material
    name = (name or '').strip()
    if not name:
        return None
    return Material.query.filter(
        Material.name == name,
        func.coalesce(Material.spec, '') == (spec or '').strip(),
    ).first()


def _generate_auto_material_code(prefix='M'):
    """为自动建档生成唯一物料编码：{prefix}{四位流水号}（如 M0001）。"""
    from app import Material
    max_number = 0
    for (code,) in Material.query.with_entities(Material.code).filter(
        Material.code.like(f'{prefix}%')
    ).all():
        m = re.match(rf'^{re.escape(prefix)}(\d+)$', code or '')
        if m:
            max_number = max(max_number, int(m.group(1)))
    for n in range(max_number + 1, max_number + 100000):
        candidate = f'{prefix}{n:04d}'
        if not Material.query.filter_by(code=candidate).first():
            return candidate
    raise ValueError('无法生成唯一物料编码')


# ==================== 语音建单：文本归一化与结构化抽取 ====================
# 需求：用户说「领8*25螺丝 1000个」→ 抽出物料关键词「8*25螺丝」+ 数量 1000。
#
# 为什么不复用 app.py 的 _ai_parse_material_lines？实测该函数在本场景直接失效：
#   「领8*25螺丝 1000个」→ 候选「25螺丝」（规格被截断，8* 丢失）
#   「领8*25螺丝」      → 空（完全解析不出）
#   「领料 螺丝8*25 1000个」→ 「螺丝」→8、「25」→1000（数量张冠李戴）
# 根因：它的正则把「数字」一律当数量，不理解「8*25」是一个整体规格。
#
# 本实现的关键差别：**先锁定规格片段，再在规格之外找数量**。

# 中文数字 → 阿拉伯（仅个位/十位组合，够覆盖规格和数量场景）
_VOICE_CN_DIGITS = {
    '零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
}

# 规格分隔符（数字之间出现时统一为 '*'）：乘/叉/杠/横杠/×/x/X/·
_VOICE_SPEC_SEPARATORS = '乘叉杠×xX*·'

# 量词表：只有「数字 + 量词」才算数量，避免把规格里的裸数字当数量
_VOICE_QUANTITY_UNITS = (
    '个', '只', '件', '套', '米', '公斤', 'kg', 'KG', '千克', '克', 'g',
    '盒', '包', '卷', '张', '片', '箱', '桶', '条', '根', '把', '付', '对',
    '支', '块', '袋', '瓶', '排', '组', '台', '盘', '捆',
)

# 建单动词前缀（剥离后剩余部分才是物料词）
_VOICE_VERB_PREFIXES = (
    '开一张', '做一张', '来一张', '建一张', '创建一个', '新建一个',
    '领料单', '出库单', '领用单',
    '领料', '领用', '领取', '出库', '领', '出', '要', '拿', '发', '给', '来',
)

# 数量词（说「一千」这类中文数量时的归一）
_VOICE_SCALE_WORDS = (('千', 1000), ('百', 100), ('十', 10))

# 同音/近音纠错（语音建单专用，补充仓库领域词表之外的口语变体）
_VOICE_HOMOPHONE_FIXES = (
    ('罗丝', '螺丝'), ('罗斯', '螺丝'), ('裸丝', '螺丝'), ('螺栓', '螺丝'),
    ('螺私', '螺丝'), ('落丝', '螺丝'),
    ('零', '领'), ('另', '领'),
    ('成', '乘'), ('称', '乘'),
)


def _voice_cn_number_to_int(token):
    """中文数字串 → 整数。支持「八」「二十五」「一百三十」「一千」；无法解析返回 None。

    累加规则（关键）：个位数字遇到「十/百/千」时要进位，而「十/百/千」之后的
    个位要**累加**而不是覆盖——否则「二十五」会被算成 5（历史上踩过这个坑）。
    """
    token = (token or '').strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    total = 0        # 已完成的高位部分
    section = 0      # 当前正在累计的个位
    pending = False  # 是否出现过「十/百/千」
    seen = False
    for ch in token:
        if ch in _VOICE_CN_DIGITS:
            section = _VOICE_CN_DIGITS[ch]
            seen = True
        elif ch in ('十', '百', '千'):
            unit = 10 if ch == '十' else (100 if ch == '百' else 1000)
            # 「十」前无数字表示 1（如「十五」=15）
            total += (section or 1) * unit
            section = 0
            pending = True
            seen = True
        else:
            return None
    return total + section if seen and (pending or section) else (section if seen else None)


def _normalize_voice_text(text):
    """把「听到的」归一成「能算的」。三层处理：同音纠错 → 中文数字 → 规格分隔符统一。

    关键：中文数字转换必须在**规格上下文**中保持分隔语义，
    「八乘二十五」→「8*25」（一个规格），而不是被拼成 825。
    """
    t = (text or '').strip()
    if not t:
        return ''

    # 1) 同音/近音纠错（长词优先，避免「零」先被替换破坏其它词）
    for wrong, right in _VOICE_HOMOPHONE_FIXES:
        t = t.replace(wrong, right)

    # 2) 中文数字 → 阿拉伯数字（含「十/百/千」组合）。
    #    必须在「乘→*」之前做：否则「八乘二十五」会先变成「八*二十五」，
    #    中文数字串被 '*' 切断，「二十五」解析失败（实测会退化成「8*5」）。
    def _cn_repl(m):
        val = _voice_cn_number_to_int(m.group(0))
        return str(val) if val is not None else m.group(0)

    t = re.sub(r'[零〇一二两三四五六七八九十百千]+', _cn_repl, t)

    # 3) 中文规格分隔符「乘/叉/杠」→ '*'（此时两侧已是阿拉伯数字）
    for sep in '乘叉杠':
        t = t.replace(sep, '*')

    # 4) 统一规格分隔符：x / X / × / · / - 在数字之间 → '*'
    t = re.sub(r'(?<=\d)\s*[xX×·]\s*(?=\d)', '*', t)
    t = re.sub(r'(?<=\d)\s*-\s*(?=\d)', '*', t)

    # 5) 压缩空白
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _parse_voice_out_text(text):
    """语音建单文本 → {keyword, quantity, spec_hint, unit}。

    核心策略（针对「8*25」被当数量的根因）：
      ① 先锁定规格片段（\\d+*\\d+），记录并**从文本中挖除**；
      ② 再在剩余文本里找「数字 + 量词」作为数量（无则 quantity=None）；
      ③ 剥离建单动词，残余即物料关键词；
      ④ 关键词为空时，用规格片段当关键词兜底。

    返回 quantity 为 None 表示「用户没说数量」，由人工填写（不猜、不编造）。
    """
    raw = (text or '').strip()
    normalized = _normalize_voice_text(raw)
    result = {
        'raw': raw,
        'normalized': normalized,
        'keyword': '',
        'quantity': None,
        'unit': '',
        'spec_hint': '',
    }
    if not normalized:
        return result

    work = normalized

    # ① 锁定规格片段：8*25 / 8*25.5 / M8*25（可带字母前缀，如 M8/M10 螺纹规格）
    #    规格可能多个，取首个为主规格（用户通常只报一个规格）
    _spec_re = r'[A-Za-z]*\d+(?:\.\d+)?(?:\*\d+(?:\.\d+)?)+'
    spec_matches = re.findall(_spec_re, work)
    spec_hint = spec_matches[0] if spec_matches else ''
    result['spec_hint'] = spec_hint
    # 挖除规格，避免其数字被当数量
    work_no_spec = re.sub(_spec_re, ' ', work)

    # ② 在「无规格」文本里找「数字 + 量词」= 真实数量
    unit_alt = '|'.join(sorted(_VOICE_QUANTITY_UNITS, key=len, reverse=True))
    qty_match = re.search(r'(\d+(?:\.\d+)?)\s*(' + unit_alt + r')', work_no_spec)
    if qty_match:
        try:
            qty = float(qty_match.group(1))
        except (TypeError, ValueError):
            qty = None
        if qty is not None and qty > 0:
            result['quantity'] = qty
            result['unit'] = qty_match.group(2)
        work_no_spec = work_no_spec.replace(qty_match.group(0), ' ', 1)

    # ③ 剥离建单动词与无意义标记词
    stem = work_no_spec
    for verb in sorted(_VOICE_VERB_PREFIXES, key=len, reverse=True):
        stem = stem.replace(verb, ' ')
    # 「规格/型号/尺寸」只是引出规格的提示词，不应混入物料关键词
    for marker in ('规格', '型号', '尺寸', '那种', '这种', '的'):
        stem = stem.replace(marker, ' ')
    # 残余里的其余数字（既非规格也非带量词数量）一并剔除，避免混入关键词
    stem = re.sub(r'\d+(?:\.\d+)?', ' ', stem)
    keyword = re.sub(r'\s+', '', stem).strip()

    # ④ 关键词兜底：没有物料词时用规格当关键词
    if not keyword and spec_hint:
        keyword = spec_hint
    result['keyword'] = keyword
    return result


# 物料名词根候选：从关键词里剥离规格后，若关键词含以下词根则用词根降级搜索
_VOICE_MATERIAL_ROOTS = (
    '螺丝', '螺栓', '螺钉', '螺帽', '螺母', '垫片', '垫圈', '轴承', '弹簧',
    '接头', '法兰', '阀门', '水管', '气管', '油管', '电缆', '电线', '气管',
    '电机', '马达', '皮带', '齿轮', '链条', '手柄', '按钮', '开关', '继电器',
    '气缸', '油缸', '滤芯', '密封圈', '扎带', '标签', '胶带', '砂纸', '钻头',
)


def _voice_split_root(keyword, spec_hint=''):
    """把关键词拆成 (词根, 规格)。词根用于降级搜索，规格用于相似度排序。

    例：'8*25螺丝' → ('螺丝', '8*25')；'螺丝' → ('螺丝', '')；
        未知词 → (关键词, 规格)，保证仍可整体搜索（不丢失用户意图）。
    """
    kw = (keyword or '').strip()
    if not kw:
        return '', (spec_hint or '').strip()
    # 关键词里若已含规格（如用户说「8*25螺丝」而规格被当关键词兜底），先摘出
    inner_spec = re.findall(r'[A-Za-z]*\d+(?:\.\d+)?(?:\*\d+(?:\.\d+)?)+', kw)
    spec = inner_spec[0] if inner_spec else (spec_hint or '').strip()
    stem = re.sub(r'[A-Za-z]*\d+(?:\.\d+)?(?:\*\d+(?:\.\d+)?)+', '', kw).strip()
    # 在残余里找已知物料词根
    for root in _VOICE_MATERIAL_ROOTS:
        if root in stem:
            return root, spec
    # 没命中词根表：整体当词根（可能是「6芯电缆」这类专有叫法）
    return (stem or kw), spec


def _voice_spec_similarity(material_spec, want_spec):
    """规格相似度打分（0~100），用于多候选排序。越像分越高。

    打分维度：完全相等 > 归一化后相等 > 数字集合重合度。
    规格为空或无法解析时给低分（不淘汰，仍可被人工选中）。
    """
    want = (want_spec or '').strip().lower().replace(' ', '')
    have = (material_spec or '').strip().lower().replace(' ', '')
    if not want:
        return 0
    if not have:
        return 10
    if have == want:
        return 100
    # 归一化：去掉分隔符再比
    compact = lambda s: re.sub(r'[*x×\-/\s]', '', s)  # noqa: E731
    if compact(have) == compact(want):
        return 95
    # 数字集合重合：8*25 vs 8*30 → {8,25} ∩ {8,30} = {8} → 覆盖率 50%
    want_nums = re.findall(r'\d+(?:\.\d+)?', want)
    have_nums = re.findall(r'\d+(?:\.\d+)?', have)
    if not want_nums:
        return 20
    hit = sum(1 for n in want_nums if n in have_nums)
    if hit == 0:
        # 规格里没有匹配数字，但若一方包含另一方（如 8*25 vs M8*25*10）仍给部分分
        return 25 if (want in have or have in want) else 0
    return int(20 + 70 * hit / len(want_nums))


def _match_voice_material(keyword, spec_hint='', warehouse=None, limit=10):
    """语音关键词 → 物料匹配（**六层降级，尽量不返回空**）。

    这是「聪明的 AI」的核心：即使「8*25螺丝」整体匹配不到，也会退到用词根
    「螺丝」搜出候选、再按规格相似度排序，让用户从最可能的几个里挑，
    而不是甩一句「没听清」。

    返回 dict：
      {
        'status': 'success' | 'multiple' | 'not_found',
        'material': Material | None,          # status=success 时给出
        'matches': [{'material':..., 'score':int, 'strategy':str}, ...],
        'root': str, 'spec': str,             # 拆解结果（诊断用）
        'strategies_tried': [str, ...],       # 试过哪些层（诊断用，便于向用户解释）
      }
    """
    from app import Material, db, joinedload

    kw = (keyword or '').strip()
    spec = (spec_hint or '').strip()
    root, spec = _voice_split_root(kw, spec)
    tried = []

    def _payload(mat, score, strategy):
        return {'material': mat, 'score': score, 'strategy': strategy}

    if not kw and not spec:
        return {'status': 'not_found', 'material': None, 'matches': [],
                'root': '', 'spec': '', 'strategies_tried': tried}

    _opts = (joinedload(Material.unit), joinedload(Material.category),
             joinedload(Material.supplier))

    # 第 1 层：别名表直查（用户上次纠正过的说法——"越用越聪明"）
    tried.append('alias')
    try:
        from app import AIMaterialAlias, _ai_material_alias_key
        for candidate in [c for c in (kw, root, f'{spec}{root}', f'{root}{spec}') if c]:
            alias_key = _ai_material_alias_key(candidate)
            if not alias_key:
                continue
            learned = AIMaterialAlias.query.options(
                joinedload(AIMaterialAlias.material).joinedload(Material.unit)
            ).filter_by(alias_key=alias_key, disabled=False).first()
            if learned and learned.material:
                return {'status': 'success', 'material': learned.material,
                        'matches': [_payload(learned.material, 100, 'alias')],
                        'root': root, 'spec': spec, 'strategies_tried': tried}
    except Exception:  # noqa: BLE001 - 别名表缺失不应影响主流程
        pass

    # 第 2 层：完整关键词精确 code
    tried.append('exact_code')
    mat = Material.query.options(*_opts).filter(
        db.func.lower(Material.code) == kw.lower()
    ).first()
    if mat:
        return {'status': 'success', 'material': mat,
                'matches': [_payload(mat, 100, 'exact_code')],
                'root': root, 'spec': spec, 'strategies_tried': tried}

    # 第 3 层：完整关键词模糊（code/name/spec）
    tried.append('fuzzy_full')
    like = f'%{kw}%'
    full_matches = Material.query.options(*_opts).filter(db.or_(
        Material.code.ilike(like),
        Material.name.ilike(like),
        Material.spec.ilike(like),
    )).order_by(Material.code.asc(), Material.id.asc()).limit(limit).all()
    if len(full_matches) == 1:
        return {'status': 'success', 'material': full_matches[0],
                'matches': [_payload(full_matches[0], 90, 'fuzzy_full')],
                'root': root, 'spec': spec, 'strategies_tried': tried}
    if len(full_matches) > 1:
        ranked = sorted(
            (_payload(m, _voice_spec_similarity(m.spec, spec), 'fuzzy_full')
             for m in full_matches),
            key=lambda x: (-x['score'], x['material'].code or ''),
        )
        return {'status': 'multiple', 'material': None, 'matches': ranked,
                'root': root, 'spec': spec, 'strategies_tried': tried}

    # 第 4 层：降级到词根搜索 + 规格相似度排序（**"聪明"的关键**）
    if root and root != kw:
        tried.append('root_fallback')
        rlike = f'%{root}%'
        root_matches = Material.query.options(*_opts).filter(db.or_(
            Material.code.ilike(rlike),
            Material.name.ilike(rlike),
            Material.spec.ilike(rlike),
        )).order_by(Material.code.asc(), Material.id.asc()).limit(50).all()
        if root_matches:
            ranked = sorted(
                (_payload(m, _voice_spec_similarity(m.spec, spec), 'root_fallback')
                 for m in root_matches),
                key=lambda x: (-x['score'], x['material'].code or ''),
            )[:limit]
            # 规格能对上（分>50）且唯一 → 直接算命中，省用户一次点选
            strong = [x for x in ranked if x['score'] >= 95]
            if len(strong) == 1:
                return {'status': 'success', 'material': strong[0]['material'],
                        'matches': ranked, 'root': root, 'spec': spec,
                        'strategies_tried': tried}
            return {'status': 'multiple', 'material': None, 'matches': ranked,
                    'root': root, 'spec': spec, 'strategies_tried': tried}

    # 第 5 层：仅用规格搜 spec 字段
    if spec:
        tried.append('spec_only')
        slike = f'%{spec}%'
        spec_matches = Material.query.options(*_opts).filter(
            Material.spec.ilike(slike)
        ).order_by(Material.code.asc(), Material.id.asc()).limit(limit).all()
        if spec_matches:
            ranked = [_payload(m, _voice_spec_similarity(m.spec, spec), 'spec_only')
                      for m in spec_matches]
            if len(ranked) == 1:
                return {'status': 'success', 'material': ranked[0]['material'],
                        'matches': ranked, 'root': root, 'spec': spec,
                        'strategies_tried': tried}
            return {'status': 'multiple', 'material': None, 'matches': ranked,
                    'root': root, 'spec': spec, 'strategies_tried': tried}

    # 第 6 层：AI 四级匹配（精确→name+spec→别名→唯一模糊）
    tried.append('ai_match')
    try:
        from app import _ai_material_match_one
        mat, reason = _ai_material_match_one(name=root or kw, spec=spec)
        if mat is not None:
            return {'status': 'success', 'material': mat,
                    'matches': [_payload(mat, 80, f'ai_{reason}')],
                    'root': root, 'spec': spec, 'strategies_tried': tried}
    except Exception:  # noqa: BLE001 - AI 匹配失败不应中断主流程
        pass

    # 全部失败：明确告知"试过什么"，不编造（符合 R5）
    return {'status': 'not_found', 'material': None, 'matches': [],
            'root': root, 'spec': spec, 'strategies_tried': tried}


# no-test:reason=路由注册辅助函数，能力由 native_api_* 与 mobile_api_* 各路由测试覆盖
def register_native_api_routes(app):
    # 装饰器为 app.py 内部定义（csrf / api_role_required / mobile_api_idempotent /
    # web_or_api_required），需在函数定义期（注册期）可用，故在 register 内延迟导入，
    # 避免 app.py 模块加载期触发循环导入。
    from app import (api_role_required, csrf, mobile_api_idempotent, web_or_api_required)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/api/csrf_refresh', methods=['POST'])
    @csrf.exempt  # 该端点本身就是为了获取新 token，不能要求带 token，否则形成鸡生蛋问题
    def api_csrf_refresh():
        from flask import current_app
        from flask_wtf.csrf import generate_csrf
        # 刷新 CSRF token
        # 用于长会话场景：客户端每 25 分钟（寿命 30 分钟）主动调用一次，
        # 更新 <meta name="csrf-token"> 标签，避免停留超过 30 分钟后所有
        # 非 GET 请求因 CSRF 失败而报错。
        # Returns: JSON: { status: 'success', csrf_token: '...' }
        # 如果全局禁用 CSRF，则直接返回空 token，由前端跳过刷新
        if not current_app.config.get('WTF_CSRF_ENABLED', True):
            return jsonify({'status': 'success', 'csrf_token': '', 'csrf_disabled': True})
        # 生成新的 CSRF token（flask_wtf 内部会自动写入 session）
        new_token = generate_csrf()
        return jsonify({'status': 'success', 'csrf_token': new_token})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/api/login', methods=['POST'])
    @csrf.exempt
    def native_api_login():
        from datetime import datetime, timedelta
        import secrets
        from werkzeug.security import check_password_hash
        from app import (ApiToken, User, add_login_log, api_json_error,
                         api_json_success, get_request_ip)
        # BUG-2026-08-11-001: WMS_NO_DB_TOUCH=1 时 auto_migrate_database 和
        # db.create_all 均被跳过，老数据库可能缺 user 登录安全列 / api_token 表 /
        # login_log 表，导致 /api/login 抛 OperationalError → 500 → nginx 502。
        # 在此兜底补建缺失的表/列，确保登录功能正常。
        _ensure_login_schema()
        try:
            payload = request.get_json(silent=True) or {}
            username = (payload.get('username') or '').strip()
            password = payload.get('password') or ''
            if not username or not password:
                return api_json_error('请输入账号和密码', 400)
            if len(username) > 80 or len(password) > 128:
                return api_json_error('用户名或密码长度不正确', 400)
            request_ip = get_request_ip()

            user = User.query.filter_by(username=username).first()
            if not user:
                add_login_log(status='failed', username=username, user=user, fail_reason='api_failed')
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return api_json_error('账号或密码错误', 401)
            if not user.is_active:
                return api_json_error('账号已被禁用', 403)
            if user.is_locked_for(request_ip):
                remaining_min = user.login_lock_remaining(request_ip)
                add_login_log(status='failed', username=username, user=user,
                              fail_reason=f'locked {remaining_min}')
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return api_json_error(f'账号已锁定，请 {remaining_min} 分钟后再试', 423)
            if not check_password_hash(user.password_hash, password):
                user.increment_failed_count(request_ip)
                add_login_log(status='failed', username=username, user=user, fail_reason='api_failed')
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return api_json_error('账号或密码错误', 401)
            if user.must_change_password:
                return api_json_error('请先通过网页登录修改初始密码', 403)

            token = ApiToken(
                token=secrets.token_urlsafe(48),
                user_id=user.id,
                expires_at=datetime.now() + timedelta(days=7),
            )
            user.last_login_at = datetime.now()
            user.last_login_ip = get_request_ip()
            user.reset_failed_count()
            add_login_log(status='success', username=username, user=user)
            db.session.add(token)
            db.session.commit()
            return api_json_success({
                'token': token.token,
                'expires_in': 7 * 24 * 60 * 60,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'name': user.username,
                    'role': user.role,
                }
            }, '登录成功')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'/api/login 异常: {e}', exc_info=True)
            # BUG-2026-08-16-019：不把内部异常细节返回客户端，避免泄露内部路径/堆栈
            return api_json_error('登录服务异常，请稍后重试', 500)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/api/inbound', methods=['POST'])
    @csrf.exempt
    @api_role_required('warehouse')
    @mobile_api_idempotent('inbound')
    def native_api_inbound(user):
        from datetime import date
        from app import (InOrder, InOrderItem, add_stock, api_json_error,
                         api_json_success, generate_order_no, location_management_enabled,
                         location_required_on_save, parse_api_lines, parse_float_value,
                         purchase_in_order_requires_order, resolve_request_warehouse,
                         round_to_2_decimals, update_location_inventory)
        from routes.print_queue import enqueue_auto_print_job
        payload = request.get_json(silent=True) or {}
        parsed, error = parse_api_lines(payload)
        if error:
            return api_json_error(error)
        business_type = (payload.get('business_type') or payload.get('type') or '').strip()
        if business_type in ('product', '产品', '产品入库'):
            business_type = '产品入库'
        elif business_type in ('purchase', '采购', '采购入库', ''):
            business_type = '采购入库'
        else:
            business_type = business_type[:50]
        if business_type == '采购入库' and purchase_in_order_requires_order():
            return api_json_error('系统要求采购入库必须关联采购订单，请从采购订单下推或选单生成入库单', 403)
        warehouse, warehouse_error = resolve_request_warehouse(payload)
        if warehouse_error:
            return api_json_error(warehouse_error, 400)
        order_warehouse = warehouse.name
        if location_management_enabled() and location_required_on_save():
            for _material, _quantity, line in parsed:
                location = (line.get('location_code') or line.get('location') or '').strip()
                if not location:
                    return api_json_error('启用库位管理后，入库必须填写库位')

        try:
            order = InOrder(
                order_no=generate_order_no('IN'),
                date=date.today(),
                warehouse=order_warehouse,
                business_type=business_type,
                purpose='Android扫码入库',
                remark='Android原生端提交',
                status='completed',
                operator_id=user.id,
                total_amount=0,
            )
            db.session.add(order)
            db.session.flush()
            total_amount = 0
            for material, quantity, line in parsed:
                price = parse_float_value(line.get('price'), material.price or 0)
                amount = round_to_2_decimals(quantity * price)
                total_amount += amount
                db.session.add(InOrderItem(
                    in_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    price=price,
                    amount=amount,
                ))
                ok, msg = add_stock(material, quantity, 'in', 'in_order', order.id, f'Android入库 {order.order_no}', warehouse=order.warehouse)
                if not ok:
                    db.session.rollback()
                    return api_json_error(msg or '库存增加失败', 500)
                location = (line.get('location_code') or line.get('location') or '').strip()
                # BUG-2026-08-18-003：客户端可能传仓库编号作为 location，
                # 关库位管理时统一为仓库名，避免流水 location 不一致。
                if location and not location_management_enabled():
                    wh_code = (order.warehouse.code or '').strip() if hasattr(order.warehouse, 'code') else ''
                    if wh_code and location == wh_code:
                        location = (order.warehouse.name or '').strip()
                loc_ok, loc_msg = update_location_inventory(material, location, quantity, warehouse=order.warehouse)
                if not loc_ok:
                    db.session.rollback()
                    return api_json_error(loc_msg or '库位库存更新失败', 500)
            order.total_amount = round_to_2_decimals(total_amount)
            enqueue_auto_print_job('in_order', order.id, order.warehouse,
                                   created_by=user.id, source_event='scan_inbound')
            db.session.commit()
            return api_json_success({'id': order.id, 'order_no': order.order_no}, '入库提交成功')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Android inbound failed')
            return api_json_error('入库提交失败', 500)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/api/outbound', methods=['POST'])
    @csrf.exempt
    @api_role_required('warehouse', 'production')
    @mobile_api_idempotent('outbound')
    def native_api_outbound(user):
        from datetime import date
        from app import (OutOrder, OutOrderItem, allow_negative_stock, api_json_error,
                         api_json_success, check_stock_sufficient, deduct_stock,
                         generate_order_no, location_management_enabled,
                         location_required_on_save, parse_api_lines, parse_float_value,
                         resolve_request_warehouse, round_to_2_decimals,
                         update_location_inventory)
        from routes.print_queue import enqueue_auto_print_job
        payload = request.get_json(silent=True) or {}
        parsed, error = parse_api_lines(payload)
        if error:
            return api_json_error(error)
        warehouse, warehouse_error = resolve_request_warehouse(payload)
        if warehouse_error:
            return api_json_error(warehouse_error, 400)
        order_warehouse = warehouse.name
        # 合同编号（选填）：命中合同档案则回填 contract_id/project_name，
        # 未命中仍保留用户输入文本（与 Web 端单据头口径一致）。
        from app import Contract
        contract_no_input = (payload.get('contract_no') or '').strip()
        contract = None
        if contract_no_input:
            contract = Contract.query.filter(
                db.func.lower(Contract.contract_no) == contract_no_input.lower()
            ).first()
        order_contract_id = contract.id if contract else None
        order_contract_no = (contract.contract_no if contract else contract_no_input) or None
        order_project_name = (contract.project_name if contract else None) or None
        if location_management_enabled() and location_required_on_save():
            for _material, _quantity, line in parsed:
                location = (line.get('location_code') or line.get('location') or '').strip()
                if not location:
                    return api_json_error('启用库位管理后，出库必须填写库位')

        if not allow_negative_stock():
            for material, quantity, _line in parsed:
                sufficient, current_stock, error_msg = check_stock_sufficient(material, quantity)
                if not sufficient:
                    return api_json_error(error_msg or f'{material.code} 库存不足，当前库存 {current_stock}')

        try:
            order = OutOrder(
                order_no=generate_order_no('OU'),
                date=date.today(),
                customer=(payload.get('receiver') or '').strip() or None,
                # BUG-2026-09-10-002：手机原生端出库此前固定写 'Android扫码出库'，
                # 与 PC 领料单（'领料单'）不是一个业务类型，后果：①每日报表领料单
                # 口径查不到手机出的库；②PC 领料单列表也看不到手机单据。
                # 手机端出库即仓库领料，统一写 '领料单'（来源仍由 purpose/remark 区分）。
                # 历史 'Android扫码出库' 单据由 daily_detail 报表口径兼容命中。
                business_type='领料单',
                warehouse=order_warehouse,
                purpose=(payload.get('department') or 'Android原生端提交').strip(),
                remark='Android原生端提交',
                status='completed',
                operator_id=user.id,
                contract_id=order_contract_id,
                contract_no=order_contract_no,
                project_name=order_project_name,
                total_amount=0,
            )
            db.session.add(order)
            db.session.flush()
            total_amount = 0
            for material, quantity, line in parsed:
                price = parse_float_value(line.get('price'), material.price or 0)
                amount = round_to_2_decimals(quantity * price)
                total_amount += amount
                db.session.add(OutOrderItem(
                    out_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    price=price,
                    amount=amount,
                    remark=(line.get('remark') or '').strip() or None,
                    # 明细级冗余合同字段（与存量单据「表头→明细」口径一致，
                    # 报表/导出读取 item.contract_no 时无需回退表头）
                    contract_id=order_contract_id,
                    contract_no=order_contract_no,
                    project_name=order_project_name,
                ))
                ok, msg = deduct_stock(material, quantity, 'out', 'out_order', order.id, f'Android出库 {order.order_no}', warehouse=order.warehouse)
                if not ok:
                    db.session.rollback()
                    return api_json_error(msg)
                # BUG-2026-08-16-020：仅开库位管理时写库位账。
                # 关闭状态下客户端若传 location，无条件写 LocationInventory 会造隐形库位账，
                # 使关库位管理的库存聚合把客户端随手填的文本当成真实库位。
                if location_management_enabled():
                    location = (line.get('location_code') or line.get('location') or '').strip()
                    ok, msg = update_location_inventory(material, location, -quantity, warehouse=order.warehouse)
                    if not ok:
                        db.session.rollback()
                        return api_json_error(msg)
            order.total_amount = round_to_2_decimals(total_amount)
            enqueue_auto_print_job('out_order', order.id, order.warehouse,
                                   created_by=user.id, source_event='scan_outbound')
            db.session.commit()
            return api_json_success({'id': order.id, 'order_no': order.order_no}, '出库提交成功')
        except Exception:
            db.session.rollback()
            app.logger.exception('Android outbound failed')
            return api_json_error('出库提交失败', 500)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/api/stocktake', methods=['POST'])
    @csrf.exempt
    @api_role_required('warehouse')
    @mobile_api_idempotent('stocktake')
    def native_api_stocktake(user):
        from datetime import date
        from app import (InventoryCheck, InventoryCheckScan, InventoryCheckScanItem,
                         Material, _acquire_order_write_lock, _apply_scan_to_batch,
                         _create_adjustment_drafts_from_check_scan,
                         _find_active_check_batch, api_json_error,
                         api_json_success, generate_order_no, get_default_warehouse,
                         get_warehouse_stock_quantities, parse_float_value,
                         location_management_enabled,
                         round_to_2_decimals, selectinload,
                         validate_inventory_warehouse)
        payload = request.get_json(silent=True) or {}
        lines = payload.get('lines') if isinstance(payload, dict) else None
        if not isinstance(lines, list) or not lines:
            return api_json_error('盘点明细不能为空')

        # BUG-2026-08-11-021：扫码盘点仓库必填，未填写时自动带入默认仓库
        warehouse = (payload.get('warehouse') or payload.get('warehouse_code') or '').strip()
        if not warehouse:
            default_wh = get_default_warehouse()
            if default_wh:
                warehouse = default_wh.name
        if not warehouse:
            return api_json_error('请选择盘点仓库', 400)
        # INV-AUDIT-005：仓库必须存在且 active（与盘点/调整等库存单据对称）
        wh_obj, wh_err = validate_inventory_warehouse(warehouse)
        if wh_err:
            return api_json_error(wh_err, 400)
        warehouse = wh_obj.name

        try:
            # INV-BATCH-001-E / BUG-2026-09-04-005：移动盘点强制选单。
            # 必须先选择 PC 端进行中的盘点单（check_id=InventoryCheck.id），
            # 明细统一 upsert 进该批次、由 PC「完成盘点」统一生成调整草稿；
            # 不再支持"无单自动建独立扫码盘点单"旁路——旧版 App（3.5.1）
            # 不带 check_id 的提交将被拒绝。
            raw_check_id = payload.get('check_id') or payload.get('checkOrderId') or ''
            try:
                check_id = int(str(raw_check_id).strip())
            except (TypeError, ValueError):
                check_id = 0
            if check_id <= 0:
                return api_json_error('请选择进行中的盘点单（在电脑端创建盘点单后选择，手机端不支持无单盘点）', 400)
            batch = db.session.get(InventoryCheck, check_id)
            if batch is None:
                return api_json_error(f'盘点单不存在：{check_id}，请刷新盘点单列表后重选', 400)
            if batch.status != 'pending':
                return api_json_error(f'盘点单 {batch.check_no} 已完结，请重新选择进行中的盘点单', 400)
            if (batch.warehouse or '').strip() != warehouse:
                return api_json_error(
                    f'盘点单 {batch.check_no} 属于仓库「{batch.warehouse}」，'
                    f'与所选盘点仓库「{warehouse}」不一致，请重新选择', 400)
            locked_batch, lock_ok = _acquire_order_write_lock(
                InventoryCheck, batch.id, 'pending',
                selectinload(InventoryCheck.items))
            if not lock_ok:
                return api_json_error(
                    f'盘点单 {batch.check_no} 正被其他操作占用（可能正在完成/反提交），请稍后重试', 400)
            batch = locked_batch
            check = InventoryCheckScan(
                check_no=generate_order_no('CS'),
                date=date.today(),
                warehouse=warehouse,
                remark=f"Android盘点：{payload.get('mode') or 'all'}",
                status='completed',
                operator_id=user.id,
                check_id=batch.id,
            )
            db.session.add(check)
            db.session.flush()
            # INV-AUDIT-003-FIX-01：盘点账面按仓库级库存取数，对齐 mobile.py scan_submit。
            # 此前默认值回退全局 Material.stock，多仓库下会把"全部仓库合计"当成
            # 单个仓库的账面数，盘盈盘亏全部算错，并据此生成错误的调整草稿。
            # 在循环外一次性聚合，避免逐行重复汇总流水（N+1）。
            warehouse_stock_map = get_warehouse_stock_quantities(wh_obj)
            for index, line in enumerate(lines, start=1):
                code = (line.get('material_code') or line.get('code') or '').strip()
                # 盘点区域（可选）：分区盘点时按"物料+区域"分行
                area = (line.get('area') or line.get('region') or line.get('location') or line.get('location_code') or '').strip()
                material = Material.query.filter_by(code=code).first()
                if not material:
                    db.session.rollback()
                    return api_json_error(f'第 {index} 行物料不存在：{code}')
                # INV-AUDIT-003-FIX-01：默认取服务端仓库级库存；客户端显式传值时
                # 仍沿用（Android ScanViewModel 固定传 null，必然走仓库级分支）。
                system_stock = parse_float_value(
                    line.get('system_stock'), warehouse_stock_map.get(material.id) or 0)
                actual_stock = parse_float_value(line.get('actual_stock'), system_stock)
                if location_management_enabled() and abs(actual_stock - system_stock) > 0.000001 and not area:
                    db.session.rollback()
                    return api_json_error(f'第 {index} 行盘点差异必须填写库位/区域', 400)
                db.session.add(InventoryCheckScanItem(
                    check_scan_id=check.id,
                    material_id=material.id,
                    area=area,
                    system_stock=system_stock,
                    actual_stock=actual_stock,
                    difference=round_to_2_decimals(actual_stock - system_stock),
                ))
            # INV-BATCH-001-E：明细 upsert 进所选批次，不独立生成草稿
            error = _apply_scan_to_batch(
                batch, check, warehouse_stock_map, operator_id=user.id)
            if error:
                db.session.rollback()
                return api_json_error(error, 400)
            db.session.commit()
            data = {
                'check_no': check.check_no,
                'batch_no': batch.check_no,
                'inventory_check_id': batch.id,
                'adjustment_nos': [],
            }
            msg = f'盘点提交成功，已挂批次 {batch.check_no}'
            return api_json_success(data, msg)
        except Exception:
            db.session.rollback()
            app.logger.exception('Android stocktake failed')
            return api_json_error('盘点提交失败', 500)

    # INV-REVERT-001 / BUG-2026-09-02-003：Android 端扫码盘点单作废入口。
    # 扫码盘点创建即 completed 且此前无任何回退路径，扫错后无法纠正。
    # 按 check_no 作废（Android 提交响应 data.check_no 回传即可撤销），
    # 核心逻辑复用 app._void_check_scan：级联删除未提交调整草稿 + 状态
    # 置 void 留痕；关联调整单已提交则拒绝（先反提交调整单）。
    # Android App 接入撤销 UI 无需后端再发版。
    @app.route('/api/stocktake/void', methods=['POST'])
    @csrf.exempt
    @api_role_required('warehouse')
    def native_api_stocktake_void(user):
        from pydantic import BaseModel, Field, field_validator
        from app import (InventoryCheckScan, _void_check_scan, api_json_error,
                         api_json_success)

        # A8：提交参数用 pydantic 输入校验（对齐 scan_submit 的契约模式）
        class StocktakeVoidRequest(BaseModel):
            check_no: str = Field(min_length=1)

            @field_validator('check_no')
            @classmethod
            def _norm(cls, v):
                v = (v or '').strip()
                if not v:
                    raise ValueError('缺少盘点单号 check_no')
                return v

        payload = request.get_json(silent=True) or {}
        try:
            req = StocktakeVoidRequest.model_validate(payload)
        except Exception as exc:
            return api_json_error(f'参数校验失败：{exc}')
        check = InventoryCheckScan.query.filter_by(check_no=req.check_no).first()
        if not check:
            return api_json_error(f'扫码盘点单不存在：{req.check_no}', 404)
        voided, deleted_nos, error, error_code = _void_check_scan(
            check.id, operator_id=user.id)
        if error:
            return api_json_error(error, 404 if error_code == 'not_found' else 400)
        msg = f'已作废扫码盘点单：{voided.check_no}'
        if deleted_nos:
            msg += f'，同步删除未提交调整草稿：{"、".join(deleted_nos)}'
        return api_json_success(
            {
                'check_id': voided.id,
                'check_no': voided.check_no,
                'deleted_adjustment_nos': deleted_nos,
            },
            msg,
        )

    @app.route('/api/stocktake/check_orders')
    @csrf.exempt
    @api_role_required('warehouse')
    def native_api_stocktake_check_orders(user):
        """Android 盘点单选择列表（INV-BATCH-001-E）。

        返回进行中（status='pending'）的 PC 盘点单；带 warehouse 参数时按仓库
        过滤（支持名称或编码），不带则返回全部。App 扫码/识物盘点先经此接口
        选单，提交时携带所选 check_id。
        """
        from app import (_list_pending_check_orders, api_json_error,
                         api_json_success, validate_inventory_warehouse)
        wh = (request.args.get('warehouse')
              or request.args.get('warehouse_code') or '').strip()
        if not wh:
            orders = _list_pending_check_orders(None)
        else:
            wh_obj, wh_err = validate_inventory_warehouse(wh)
            if wh_err:
                return api_json_error(wh_err, 400)
            orders = _list_pending_check_orders(wh_obj.name)
        return api_json_success({'orders': orders})

    @app.route('/api/mobile/dashboard')
    @csrf.exempt
    @web_or_api_required
    def mobile_api_dashboard():
        """移动端首页概览：今日进出统计、待处理数、库存告警（按仓库隔离）。

        BUG-2026-09-10-010：多仓用户（4 个以上仓库）反馈首页"今日入库/出库"数字
        明显偏小甚至为 0——首页此前不带仓库参数、服务端一律回退默认仓库，录在其他
        仓的单据全部不计入。现与每日报表（BUG-2026-09-10-009）口径统一：
        - warehouse_id / warehouse_code / warehouse → 指定仓库（缺省回退默认仓库，
          AGENTS.md 仓库必填）
        - 显式传 `all` → 全部仓库汇总（用户主动跨仓，不是"未指定仓库"，不违反必填）
        """
        from datetime import date
        from sqlalchemy import func
        from app import (InOrder, InOrderItem, Material, OutOrder, OutOrderItem,
                         api_json_error, api_json_success, get_warehouse_stock_quantities,
                         inventory_alert_enabled, resolve_request_warehouse)
        # 全部仓库汇总模式：显式 all 才跨仓，否则仍按仓库必填规则解析
        raw_wh_param = str(request.args.get('warehouse_id')
                           or request.args.get('warehouse_code')
                           or request.args.get('warehouse') or '').strip()
        all_warehouses = raw_wh_param.lower() == 'all'
        if all_warehouses:
            warehouse, wh_err = None, None
        else:
            warehouse, wh_err = resolve_request_warehouse(request.args)
            if wh_err:
                return api_json_error(wh_err, 400)
        warehouse_name = (warehouse.name or '') if warehouse else ''
        # 单仓模式加仓库条件；全部仓库模式不加（含历史 warehouse 为空的脏数据，
        # 避免漏数，R2）
        wh_filters = [] if all_warehouses else [
            InOrder.warehouse == warehouse_name
        ]
        out_wh_filters = [] if all_warehouses else [
            OutOrder.warehouse == warehouse_name
        ]
        today = date.today()

        # 今日入库统计
        today_in_count = InOrder.query.filter(
            InOrder.date == today,
            InOrder.status == 'completed',
            *wh_filters,
        ).count()
        today_in_items = db.session.query(func.coalesce(func.sum(InOrderItem.quantity), 0)).join(
            InOrder, InOrderItem.in_order_id == InOrder.id
        ).filter(
            InOrder.date == today,
            InOrder.status == 'completed',
            *wh_filters,
        ).scalar() or 0

        # 今日出库统计
        today_out_count = OutOrder.query.filter(
            OutOrder.date == today,
            OutOrder.status == 'completed',
            *out_wh_filters,
        ).count()
        today_out_items = db.session.query(func.coalesce(func.sum(OutOrderItem.quantity), 0)).join(
            OutOrder, OutOrderItem.out_order_id == OutOrder.id
        ).filter(
            OutOrder.date == today,
            OutOrder.status == 'completed',
            *out_wh_filters,
        ).scalar() or 0

        # 待处理入库单
        pending_in = InOrder.query.filter(
            InOrder.status == 'pending', *wh_filters
        ).count()

        # 待处理出库单
        pending_out = OutOrder.query.filter(
            OutOrder.status == 'pending', *out_wh_filters
        ).count()

        # 库存告警（按仓库级数量判定，不读全局 Material.stock）
        alert_count = 0
        if inventory_alert_enabled():
            candidates = Material.query.filter(Material.min_stock > 0).all()
            if all_warehouses:
                # 全部仓库汇总：逐仓判定，任一仓低于最低库存即计一次告警
                # （同一物料在多仓告警只算一条，避免重复计数）
                from app import Warehouse as _Warehouse
                alert_material_ids = set()
                for wh in _Warehouse.query.filter_by(status='active').all():
                    quantities = get_warehouse_stock_quantities(wh)
                    for m in candidates:
                        if quantities.get(m.id, 0) <= (m.min_stock or 0):
                            alert_material_ids.add(m.id)
                alert_count = len(alert_material_ids)
            else:
                quantities = get_warehouse_stock_quantities(warehouse)
                alert_count = sum(
                    1 for m in candidates
                    if quantities.get(m.id, 0) <= (m.min_stock or 0)
                )

        return api_json_success({
            'today_in_orders': today_in_count,
            'today_in_quantity': float(today_in_items),
            'today_out_orders': today_out_count,
            'today_out_quantity': float(today_out_items),
            'pending_in_orders': pending_in,
            'pending_out_orders': pending_out,
            'alert_count': alert_count,
            'date': today.isoformat(),
            # BUG-2026-09-10-010：回传仓库上下文，手机端可显示"当前口径是哪个仓"
            'warehouse': '全部仓库' if all_warehouses else warehouse_name,
            'warehouse_id': None if all_warehouses else (warehouse.id if warehouse else None),
            'all_warehouses': all_warehouses,
        })

    @app.route('/api/mobile/stock/query')
    @csrf.exempt
    @web_or_api_required
    def mobile_api_stock_query():
        """移动端库存查询：多条件模糊搜索 + 分页（按仓库级数量）"""
        from sqlalchemy.orm import joinedload
        from app import (MOBILE_API_PAGE_SIZE_DEFAULT, Material, _mobile_paginate,
                         api_json_error, api_json_success, get_warehouse_stock_quantities,
                         normalize_stock_quantity, resolve_request_warehouse,
                         round_to_2_decimals)
        # BUG-2026-08-12-004：仓库必填
        warehouse, wh_err = resolve_request_warehouse(request.args)
        if wh_err:
            return api_json_error(wh_err, 400)
        keyword = (request.args.get('keyword') or request.args.get('kw') or '').strip()
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', MOBILE_API_PAGE_SIZE_DEFAULT, type=int)

        query = Material.query.options(
            joinedload(Material.unit),
            joinedload(Material.category),
            joinedload(Material.supplier),
        )

        if keyword:
            like = f'%{keyword}%'
            query = query.filter(db.or_(
                Material.code.like(like),
                Material.name.like(like),
                Material.spec.like(like),
            ))

        query = query.order_by(Material.code.asc())

        result = _mobile_paginate(query, page, page_size)
        materials = result['items']
        # 仓库级数量汇总；无记录的物料按 0 处理，绝不回退全局 Material.stock
        quantities = get_warehouse_stock_quantities(warehouse)

        return api_json_success({
            'items': [
                {
                    'id': m.id,
                    'code': m.code or '',
                    'name': m.name or '',
                    'spec': m.spec or '',
                    'unit': m.unit.name if m.unit else '',
                    'category': m.category.name if m.category else '',
                    'supplier': m.supplier.name if m.supplier else '',
                    'stock': normalize_stock_quantity(quantities.get(m.id, 0)),
                    'price': round_to_2_decimals(m.price or 0),
                    'min_stock': m.min_stock or 0,
                    'reorder_point': m.reorder_point or 0,
                }
                for m in materials
            ],
            'total': result['total'],
            'page': result['page'],
            'page_size': result['page_size'],
            'total_pages': result['total_pages'],
        })

    @app.route('/api/mobile/alert/list')
    @csrf.exempt
    @web_or_api_required
    def mobile_api_alert_list():
        """移动端库存告警列表：仓库级库存低于最低库存的物料"""
        from sqlalchemy.orm import joinedload
        from app import (MOBILE_API_PAGE_SIZE_DEFAULT, MOBILE_API_PAGE_SIZE_MAX, Material,
                         api_json_error, api_json_success, get_warehouse_stock_quantities,
                         inventory_alert_enabled, normalize_stock_quantity,
                         resolve_request_warehouse)
        # BUG-2026-08-12-004：仓库必填
        warehouse, wh_err = resolve_request_warehouse(request.args)
        if wh_err:
            return api_json_error(wh_err, 400)
        if not inventory_alert_enabled():
            return api_json_success({
                'items': [],
                'total': 0,
                'page': 1,
                'page_size': MOBILE_API_PAGE_SIZE_DEFAULT,
                'total_pages': 0,
            }, '库存预警未启用')

        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', MOBILE_API_PAGE_SIZE_DEFAULT, type=int)
        page = max(1, page or 1)
        page_size = min(max(1, page_size or MOBILE_API_PAGE_SIZE_DEFAULT), MOBILE_API_PAGE_SIZE_MAX)

        # 仓库级数量汇总；低库存判定针对解析仓库，不读全局 Material.stock
        quantities = get_warehouse_stock_quantities(warehouse)
        candidates = Material.query.options(
            joinedload(Material.unit),
            joinedload(Material.category),
            joinedload(Material.supplier),
        ).filter(
            Material.min_stock > 0,
        ).order_by(Material.code.asc()).all()
        alerted = [
            m for m in candidates
            if normalize_stock_quantity(quantities.get(m.id, 0)) <= (m.min_stock or 0)
        ]
        alerted.sort(key=lambda m: (normalize_stock_quantity(quantities.get(m.id, 0)), m.code or ''))

        total = len(alerted)
        materials = alerted[(page - 1) * page_size: page * page_size]

        return api_json_success({
            'items': [
                {
                    'id': m.id,
                    'code': m.code or '',
                    'name': m.name or '',
                    'spec': m.spec or '',
                    'unit': m.unit.name if m.unit else '',
                    'stock': normalize_stock_quantity(quantities.get(m.id, 0)),
                    'min_stock': m.min_stock or 0,
                    'reorder_point': m.reorder_point or 0,
                    'gap': max(0, (m.min_stock or 0) - normalize_stock_quantity(quantities.get(m.id, 0))),
                }
                for m in materials
            ],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size) if total > 0 else 0,
        })

    @app.route('/api/mobile/in_order/list')
    @csrf.exempt
    @web_or_api_required
    def mobile_api_in_order_list():
        """移动端入库单列表：分页 + 状态筛选（按仓库隔离）"""
        from sqlalchemy.orm import joinedload
        from app import (MOBILE_API_PAGE_SIZE_DEFAULT, InOrder, InOrderItem, Material,
                         _in_order_payload, _mobile_paginate, api_json_error,
                         api_json_success, resolve_request_warehouse)
        # BUG-2026-08-12-004：仓库必填
        warehouse, wh_err = resolve_request_warehouse(request.args)
        if wh_err:
            return api_json_error(wh_err, 400)
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', MOBILE_API_PAGE_SIZE_DEFAULT, type=int)
        status = (request.args.get('status') or '').strip()
        keyword = (request.args.get('keyword') or '').strip()

        query = InOrder.query.options(
            joinedload(InOrder.operator),
            joinedload(InOrder.items).joinedload(InOrderItem.material),
        ).filter(InOrder.warehouse == (warehouse.name or ''))

        if status and status in ('pending', 'completed'):
            query = query.filter(InOrder.status == status)
        if keyword:
            like = f'%{keyword}%'
            query = query.filter(InOrder.order_no.like(like))

        query = query.order_by(InOrder.created_at.desc(), InOrder.id.desc())

        result = _mobile_paginate(query, page, page_size)
        orders = result['items']

        return api_json_success({
            'items': [_in_order_payload(o) for o in orders],
            'total': result['total'],
            'page': result['page'],
            'page_size': result['page_size'],
            'total_pages': result['total_pages'],
        })

    @app.route('/api/mobile/in_order/<int:order_id>')
    @csrf.exempt
    @web_or_api_required
    def mobile_api_in_order_detail(order_id):
        """移动端入库单详情（按仓库隔离，跨仓返回 404）"""
        from sqlalchemy.orm import joinedload
        from app import (InOrder, InOrderItem, Material, Unit, _in_order_detail_payload,
                         api_json_error, api_json_success, resolve_request_warehouse)
        # BUG-2026-08-12-004：仓库必填
        warehouse, wh_err = resolve_request_warehouse(request.args)
        if wh_err:
            return api_json_error(wh_err, 400)
        order = InOrder.query.options(
            joinedload(InOrder.operator),
            joinedload(InOrder.supplier),
            joinedload(InOrder.items).joinedload(InOrderItem.material).joinedload(Material.unit),
        ).get(order_id)

        if not order or (order.warehouse or '') != (warehouse.name or ''):
            return api_json_error('入库单不存在', 404)

        return api_json_success(_in_order_detail_payload(order))

    @app.route('/api/mobile/out_order/list')
    @csrf.exempt
    @web_or_api_required
    def mobile_api_out_order_list():
        """移动端出库单列表：分页 + 状态筛选（按仓库隔离）"""
        from sqlalchemy.orm import joinedload
        from app import (MOBILE_API_PAGE_SIZE_DEFAULT, OutOrder, OutOrderItem, Material,
                         _mobile_paginate, _out_order_payload, api_json_error,
                         api_json_success, resolve_request_warehouse)
        # BUG-2026-08-12-004：仓库必填
        warehouse, wh_err = resolve_request_warehouse(request.args)
        if wh_err:
            return api_json_error(wh_err, 400)
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', MOBILE_API_PAGE_SIZE_DEFAULT, type=int)
        status = (request.args.get('status') or '').strip()
        keyword = (request.args.get('keyword') or '').strip()

        query = OutOrder.query.options(
            joinedload(OutOrder.operator),
            joinedload(OutOrder.department),
            joinedload(OutOrder.items).joinedload(OutOrderItem.material),
        ).filter(OutOrder.warehouse == (warehouse.name or ''))

        if status and status in ('pending', 'completed'):
            query = query.filter(OutOrder.status == status)
        if keyword:
            like = f'%{keyword}%'
            query = query.filter(OutOrder.order_no.like(like))

        query = query.order_by(OutOrder.created_at.desc(), OutOrder.id.desc())

        result = _mobile_paginate(query, page, page_size)
        orders = result['items']

        return api_json_success({
            'items': [_out_order_payload(o) for o in orders],
            'total': result['total'],
            'page': result['page'],
            'page_size': result['page_size'],
            'total_pages': result['total_pages'],
        })

    @app.route('/api/mobile/out_order/<int:order_id>')
    @csrf.exempt
    @web_or_api_required
    def mobile_api_out_order_detail(order_id):
        """移动端出库单详情（按仓库隔离，跨仓返回 404）"""
        from sqlalchemy.orm import joinedload
        from app import (OutOrder, OutOrderItem, Material, Unit, _out_order_detail_payload,
                         api_json_error, api_json_success, resolve_request_warehouse)
        # BUG-2026-08-12-004：仓库必填
        warehouse, wh_err = resolve_request_warehouse(request.args)
        if wh_err:
            return api_json_error(wh_err, 400)
        order = OutOrder.query.options(
            joinedload(OutOrder.operator),
            joinedload(OutOrder.department),
            joinedload(OutOrder.items).joinedload(OutOrderItem.material).joinedload(Material.unit),
        ).get(order_id)

        if not order or (order.warehouse or '') != (warehouse.name or ''):
            return api_json_error('出库单不存在', 404)

        return api_json_success(_out_order_detail_payload(order))

    @app.route('/api/mobile/contracts')
    @csrf.exempt
    @web_or_api_required
    def mobile_api_contracts_search():
        """移动端合同编号模糊搜索（出库单等选填合同字段的快速匹配）。

        keyword 片段大小写不敏感包含匹配 contract_no / project_name：
        如输入 0709 可匹配 HD260709。仅返回启用状态合同，最多 20 条。
        """
        from app import Contract, api_json_success
        keyword = (request.args.get('keyword') or request.args.get('q') or '').strip()
        query = Contract.query.filter(Contract.status == 'active')
        if keyword:
            like = f'%{keyword}%'
            query = query.filter(db.or_(
                Contract.contract_no.ilike(like),
                Contract.project_name.ilike(like),
            ))
        contracts = query.order_by(Contract.contract_no).limit(20).all()
        return api_json_success({
            'items': [{
                'id': c.id,
                'contract_no': c.contract_no or '',
                'project_name': c.project_name or '',
            } for c in contracts]
        })

    @app.route('/api/mobile/report/daily_detail')
    @csrf.exempt
    @web_or_api_required
    def mobile_api_report_daily_detail():
        """移动端每日明细报表：按日期 + 业务类型查看明细行（默认按仓库隔离）。

        供手机端报表页使用：
        - type=purchase_in  → 当日采购入库单明细
        - type=requisition  → 当日领料单明细
        - warehouse_id / warehouse_code / warehouse → 指定仓库（缺省回退默认仓库，
          AGENTS.md 仓库必填）；显式传 `all` 表示**全部仓库汇总**（用户主动跨仓，
          不是"未指定仓库"，不违反仓库必填规则）
        仅统计已完成单据；汇总基于全集（不受分页影响）。
        """
        from datetime import date as _date, datetime as _dt
        from sqlalchemy import func
        from sqlalchemy.orm import joinedload
        from app import (MOBILE_API_PAGE_SIZE_DEFAULT, InOrder, InOrderItem, Material,
                         OutOrder, OutOrderItem, _mobile_paginate, api_json_error,
                         api_json_success, normalize_stock_quantity,
                         resolve_request_warehouse, round_to_2_decimals)
        # BUG-2026-09-10-009：多仓用户（4 个以上仓库）反馈日报"查不到今天的记录"——
        # 手机报表页此前没有仓库参数，服务端一律回退默认仓库，录在其他仓的单据全部
        # 看不到。现支持显式指定仓库，以及 warehouse_id=all 的全部仓库汇总。
        raw_wh_param = str(request.args.get('warehouse_id')
                           or request.args.get('warehouse_code')
                           or request.args.get('warehouse') or '').strip()
        all_warehouses = raw_wh_param.lower() == 'all'
        if all_warehouses:
            warehouse, wh_err = None, None
        else:
            warehouse, wh_err = resolve_request_warehouse(request.args)
            if wh_err:
                return api_json_error(wh_err, 400)

        TYPE_DEFS = {
            'purchase_in': {
                'label': '采购入库', 'order_model': InOrder, 'item_model': InOrderItem,
                'join_cond': InOrderItem.in_order_id == InOrder.id,
                'business_types': ('采购入库',), 'match_null_type': False,
                'party_key': 'supplier',
            },
            'requisition': {
                'label': '领料单', 'order_model': OutOrder, 'item_model': OutOrderItem,
                'join_cond': OutOrderItem.out_order_id == OutOrder.id,
                # BUG-2026-09-10-001：手机原生端 /api/outbound 历史上固定写
                # business_type='Android扫码出库'，严格等值 '领料单' 会让手机扫的
                # 出库在每日报表里一条都不出现（首页"今日出库"却显示有数，口径自相
                # 矛盾）。改为业务类型集合匹配，并兼容历史脏数据（类型为空按领料计，
                # 与 PC 领料单列表 out_order_list 口径一致）。
                'business_types': ('领料单', 'Android扫码出库'), 'match_null_type': True,
                'party_key': 'department',
            },
        }
        report_type = (request.args.get('type') or '').strip()
        cfg = TYPE_DEFS.get(report_type)
        if cfg is None:
            return api_json_error('报表类型无效，支持 purchase_in（采购入库）/ requisition（领料单）', 400)

        raw_date = (request.args.get('date') or '').strip()
        if raw_date:
            try:
                target_date = _dt.strptime(raw_date, '%Y-%m-%d').date()
            except ValueError:
                return api_json_error('日期格式无效，应为 YYYY-MM-DD', 400)
        else:
            target_date = _date.today()

        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', MOBILE_API_PAGE_SIZE_DEFAULT, type=int)

        OrderModel, ItemModel = cfg['order_model'], cfg['item_model']
        wh_name = (warehouse.name or '') if warehouse else ''
        # 业务类型口径：集合匹配 +（可选）空类型兜底，见 TYPE_DEFS 注释。
        type_conds = [OrderModel.business_type == bt for bt in cfg['business_types']]
        if cfg['match_null_type']:
            type_conds.append(OrderModel.business_type.is_(None))
        type_filter = db.or_(*type_conds) if len(type_conds) > 1 else type_conds[0]
        # 全部仓库模式不加仓库条件（含历史 warehouse 为空的脏数据，避免漏数，R2）
        wh_filters = [] if all_warehouses else [OrderModel.warehouse == wh_name]
        base_filters = wh_filters + [
            type_filter,
            OrderModel.status == 'completed',
            OrderModel.date == target_date,
        ]

        # 汇总基于全集：单据数 / 明细数 / 总数量 / 总金额
        agg = db.session.query(
            func.count(ItemModel.id),
            func.coalesce(func.sum(ItemModel.quantity), 0.0),
            func.coalesce(func.sum(ItemModel.amount), 0.0),
            func.count(func.distinct(OrderModel.id)),
        ).join(OrderModel, cfg['join_cond']).filter(*base_filters).one()

        if report_type == 'purchase_in':
            query = (ItemModel.query
                     .join(InOrder, InOrderItem.in_order_id == InOrder.id)
                     .join(Material, ItemModel.material_id == Material.id)
                     .options(
                         joinedload(InOrderItem.in_order).joinedload(InOrder.supplier),
                         joinedload(InOrderItem.in_order).joinedload(InOrder.operator),
                         joinedload(InOrderItem.material).joinedload(Material.unit),
                     )
                     .filter(*base_filters)
                     .order_by(InOrder.order_no.desc(), InOrderItem.id.desc()))
        else:
            query = (ItemModel.query
                     .join(OutOrder, OutOrderItem.out_order_id == OutOrder.id)
                     .join(Material, ItemModel.material_id == Material.id)
                     .options(
                         joinedload(OutOrderItem.out_order).joinedload(OutOrder.department),
                         joinedload(OutOrderItem.out_order).joinedload(OutOrder.operator),
                         joinedload(OutOrderItem.material).joinedload(Material.unit),
                     )
                     .filter(*base_filters)
                     .order_by(OutOrder.order_no.desc(), OutOrderItem.id.desc()))

        result = _mobile_paginate(query, page, page_size)
        rows = []
        for item in result['items']:
            order = item.in_order if report_type == 'purchase_in' else item.out_order
            material = item.material
            party = order.supplier if report_type == 'purchase_in' else order.department
            rows.append({
                'order_id': order.id,
                'order_no': order.order_no or '',
                'date': order.date.isoformat() if order.date else '',
                # BUG-2026-09-10-009：全部仓库汇总模式下必须能看出每行属于哪个仓
                'warehouse': order.warehouse or '',
                'material_code': material.code if material else '',
                'material_name': material.name if material else '',
                # BUG-2026-08-24-007：material.spec 列可空，显式 null 会让 Gson
                # （绕过构造器默认值）把 App 端非空字段置 null 引发 NPE，统一兜底为 ''
                'spec': (material.spec if material else '') or '',
                'unit': material.unit.name if material and material.unit else '',
                'quantity': normalize_stock_quantity(item.quantity or 0),
                'price': round_to_2_decimals(item.price or 0),
                'amount': round_to_2_decimals(item.amount or 0),
                cfg['party_key']: party.name if party else '',
                'operator': order.operator.username if order.operator else '',
                # 手机端报表展示合同编号（明细级优先，回退单据头）
                'contract_no': (item.contract_no or order.contract_no or ''),
                'remark': item.remark or '',
            })

        # 诊断信息（BUG-2026-09-10-001）：报表只统计「已完成」单据，而 PC 端入库/出库
        # 保存后默认是 pending（需人工点完成），手机端因此表现为"今天的记录查不到"
        # 却没有任何线索。这里回传查询仓库、服务器当天日期、待完成单据数、以及当天
        # 该仓已完成但业务类型不在本报表口径内的单据分布，供手机端给出明确提示。
        pending_orders = OrderModel.query.filter(
            *wh_filters,
            OrderModel.date == target_date,
            db.or_(OrderModel.status != 'completed', OrderModel.status.is_(None)),
        ).count()
        other_type_orders = []
        for biz_type, order_cnt in db.session.query(
            OrderModel.business_type, func.count(func.distinct(OrderModel.id))
        ).filter(
            *wh_filters,
            OrderModel.date == target_date,
            OrderModel.status == 'completed',
            ~type_filter,
        ).group_by(OrderModel.business_type).all():
            if order_cnt:
                other_type_orders.append({
                    'business_type': biz_type or '未填写',
                    'orders': order_cnt,
                })
        other_type_orders.sort(key=lambda row: (-row['orders'], row['business_type']))
        matched_types = list(cfg['business_types'])
        if cfg['match_null_type']:
            matched_types.append('未填写')

        return api_json_success({
            'date': target_date.isoformat(),
            'type': report_type,
            'type_label': cfg['label'],
            'warehouse': '全部仓库' if all_warehouses else wh_name,
            'warehouse_id': None if all_warehouses else (warehouse.id if warehouse else None),
            'all_warehouses': all_warehouses,
            'server_today': _date.today().isoformat(),
            'diagnostics': {
                'business_types': matched_types,
                'pending_orders': pending_orders,
                'other_type_orders': other_type_orders,
            },
            'summary': {
                'order_count': agg[3],
                'item_count': agg[0],
                'quantity': round_to_2_decimals(agg[1]),
                'amount': round_to_2_decimals(agg[2]),
            },
            'items': rows,
            'total': result['total'],
            'page': result['page'],
            'page_size': result['page_size'],
            'total_pages': result['total_pages'],
        })

    @app.route('/api/mobile/profile')
    @csrf.exempt
    @web_or_api_required
    def mobile_api_profile():
        """移动端个人中心：用户信息"""
        from flask_login import current_user
        from app import api_json_error, api_json_success, get_bearer_user
        user = get_bearer_user() or current_user
        if not user or not user.is_authenticated:
            return api_json_error('未登录', 401)

        return api_json_success({
            'id': user.id,
            'username': user.username,
            'name': user.username,
            'role': user.role,
            'last_login_at': user.last_login_at.isoformat() if user.last_login_at else '',
            'last_login_ip': user.last_login_ip or '',
            'must_change_password': user.must_change_password or False,
        })

    @app.route('/api/warehouses')
    @web_or_api_required
    def native_api_warehouses():
        """移动端仓库列表：返回启用的仓库，供期初建账等场景选择"""
        from app import Warehouse, api_json_success
        warehouses = Warehouse.query.filter_by(status='active').order_by(Warehouse.code.asc(), Warehouse.id.asc()).all()
        return api_json_success({
            'items': [
                {'id': w.id, 'code': w.code or '', 'name': w.name or ''}
                for w in warehouses
            ]
        })

    @app.route('/api/opening_stock')
    @web_or_api_required
    def native_api_opening_stock_list():
        """移动端期初库存列表：按解析仓库过滤，返回建账日期等信息"""
        from sqlalchemy.orm import joinedload
        from app import (OpeningStock, api_json_error, api_json_success,
                         normalize_stock_quantity, resolve_request_warehouse,
                         round_to_2_decimals)
        # BUG-2026-08-12-004：仓库必填——未传参时带入默认仓库，无默认仓库返回 400
        warehouse, wh_err = resolve_request_warehouse(request.args)
        if wh_err:
            return api_json_error(wh_err, 400)
        keyword = (request.args.get('keyword') or '').strip()

        query = OpeningStock.query.options(
            joinedload(OpeningStock.material),
            joinedload(OpeningStock.warehouse),
        ).filter(OpeningStock.warehouse_id == warehouse.id)
        if keyword:
            from app import Material
            like = f'%{keyword}%'
            query = query.join(Material, OpeningStock.material_id == Material.id).filter(
                db.or_(
                    Material.code.like(like),
                    Material.name.like(like),
                    Material.spec.like(like),
                )
            )

        items = query.order_by(OpeningStock.created_at.desc(), OpeningStock.id.desc()).limit(200).all()
        return api_json_success({
            'items': [
                {
                    'id': o.id,
                    'material_code': o.material.code if o.material else '',
                    'material_name': o.material.name if o.material else '',
                    'spec': o.material.spec if o.material else '',
                    'unit': o.material.unit.name if o.material and o.material.unit else '',
                    'warehouse_id': o.warehouse_id,
                    'warehouse_name': o.warehouse.name if o.warehouse else '',
                    'date': o.date.isoformat() if o.date else '',
                    'quantity': normalize_stock_quantity(o.quantity or 0),
                    'price': round_to_2_decimals(o.price or 0),
                    'amount': round_to_2_decimals(o.amount or 0),
                }
                for o in items
            ]
        })

    # pydantic:reason=存量起步按手写校验，pydantic 迁移另行任务
    @app.route('/api/opening_stock', methods=['POST'])
    @csrf.exempt
    @api_role_required('warehouse')
    @mobile_api_idempotent('opening_stock')
    def native_api_opening_stock_submit(user):
        """移动端期初建账提交：选择日期+仓库，扫码录入物料行"""
        from app import (Material, OpeningStock, Warehouse,
                         _apply_opening_stock_balance, _parse_opening_stock_date,
                         api_json_error, api_json_success, normalize_stock_quantity,
                         parse_float_value, round_to_2_decimals)
        payload = request.get_json(silent=True) or {}
        lines = payload.get('lines') if isinstance(payload, dict) else None
        if not isinstance(lines, list) or not lines:
            return api_json_error('期初库存明细不能为空', 400)

        warehouse_code = (payload.get('warehouse_code') or payload.get('warehouse') or '').strip()
        if not warehouse_code:
            return api_json_error('请选择仓库', 400)
        warehouse = Warehouse.query.filter(
            (Warehouse.code == warehouse_code) | (Warehouse.name == warehouse_code)
        ).first()
        if not warehouse:
            return api_json_error(f'仓库不存在：{warehouse_code}', 400)
        if (warehouse.status or 'active') != 'active':
            return api_json_error(f'仓库 [{warehouse.name}] 已停用，禁止期初建账', 403)
        doc_date = _parse_opening_stock_date(payload.get('date'))

        try:
            saved = []
            for index, line in enumerate(lines, start=1):
                if not isinstance(line, dict):
                    return api_json_error(f'第 {index} 行格式错误', 400)
                code = (line.get('material_code') or line.get('code') or '').strip()
                if not code:
                    return api_json_error(f'第 {index} 行缺少物料编码', 400)
                material = Material.query.filter_by(code=code).first()
                if not material:
                    return api_json_error(f'第 {index} 行物料不存在：{code}', 400)
                raw_qty = str(line.get('quantity') if line.get('quantity') is not None else '').strip()
                if raw_qty == '':
                    return api_json_error(f'第 {index} 行请输入数量', 400)
                try:
                    quantity = float(raw_qty)
                except (TypeError, ValueError):
                    return api_json_error(f'第 {index} 行数量格式不正确', 400)
                if quantity < 0:
                    return api_json_error(f'第 {index} 行期初数量不能小于 0', 400)
                quantity = normalize_stock_quantity(quantity)
                price = round_to_2_decimals(parse_float_value(line.get('price'), material.price or 0))
                amount = round_to_2_decimals(quantity * price)
                remark = (line.get('remark') or '').strip() or None

                opening = OpeningStock.query.filter_by(
                    material_id=material.id, warehouse_id=warehouse.id
                ).with_for_update().first()
                opening, _delta = _apply_opening_stock_balance(
                    opening, material, quantity, price, amount, remark, warehouse, doc_date
                )
                opening.operator_id = user.id
                saved.append({'material_code': code, 'quantity': quantity, 'price': price})
            db.session.commit()
            return api_json_success({'count': len(saved), 'lines': saved}, f'期初库存已保存，共 {len(saved)} 行')
        except Exception:
            db.session.rollback()
            app.logger.exception('Android opening stock submit failed')
            return api_json_error('期初库存提交失败', 500)

    @app.route('/api/categories')
    @web_or_api_required
    def api_categories():
        from app import MaterialCategory
        cats = MaterialCategory.query.all()
        return jsonify([{'id': c.id, 'code': c.code, 'name': c.name} for c in cats])

    @app.route('/api/units')
    @web_or_api_required
    def api_units():
        from app import Unit, serialize_unit
        units = Unit.query.order_by(Unit.code.asc(), Unit.id.asc()).all()
        return jsonify([serialize_unit(unit) for unit in units])

    @app.route('/api/suppliers')
    @web_or_api_required
    def api_suppliers():
        from app import Supplier, serialize_supplier
        suppliers = Supplier.query.order_by(Supplier.code.asc(), Supplier.id.asc()).all()
        return jsonify([serialize_supplier(supplier) for supplier in suppliers])

    @app.route('/api/customers')
    @web_or_api_required
    def api_customers():
        from app import Customer, serialize_customer
        customers = Customer.query.order_by(Customer.code.asc(), Customer.id.asc()).all()
        return jsonify([serialize_customer(customer) for customer in customers])

    # pydantic:reason=新增移动端识别单据确认端点，按 A8 要求使用 pydantic 输入校验
    @app.route('/api/mobile/inbound_draft', methods=['POST'])
    @csrf.exempt
    @api_role_required('warehouse', 'purchase')
    @mobile_api_idempotent('inbound_draft')
    def native_api_inbound_draft(user):
        """移动端识别单据确认后生成入库草稿（status=pending）。

        拦截未匹配到建档物料的识别行；仓库必填（未传入时尝试自动带入默认仓库）。
        生成的是 pending 草稿，不直接加库存，需在职员确认后才正式入库。
        """
        from datetime import date
        from pydantic import BaseModel, Field, field_validator
        from app import (InOrder, InOrderItem, Material, Warehouse,
                         api_json_error, api_json_success, generate_order_no,
                         get_default_warehouse, location_management_enabled,
                         location_required_on_save, purchase_in_order_requires_order,
                         round_to_2_decimals)

        class InboundDraftLine(BaseModel):
            material_code: str = Field(min_length=1)
            quantity: float = Field(gt=0)
            price: float | None = None
            # 自动建档字段：当物料档案无此名称/型号时，据 name/spec/unit 自动建档
            name: str | None = None
            spec: str | None = None
            unit: str | None = None

        class InboundDraftRequest(BaseModel):
            lines: list[InboundDraftLine] = Field(min_length=1)
            business_type: str = '其他入库'
            warehouse: str | None = None
            warehouse_code: str | None = None
            remark: str | None = None
            # 置 True 时，未匹配到建档物料的识别行将按 name/spec/unit 自动建档
            auto_create_material: bool = False

            @field_validator('business_type')
            @classmethod
            def normalize_business_type(cls, v):  # no-test:reason=字段归一化逻辑已在 verify_mobile_inbound_draft_api.py 的确认流程测试中覆盖
                v = (v or '').strip()
                if v in ('product', '产品', '产品入库'):
                    return '产品入库'
                if v in ('purchase', '采购', '采购入库'):
                    return '采购入库'
                return (v or '其他入库')[:50]

        payload = request.get_json(silent=True) or {}
        try:
            req = InboundDraftRequest.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - pydantic 校验错误统一转为 400
            return api_json_error(f'参数校验失败：{exc}', 400)

        try:
            # 解析物料行：能匹配建档物料则使用建档物料；
            # 未匹配时若启用自动建档则按 name/spec/unit 自动建档，否则拦截。
            matched = []
            unmatched = []
            auto_created = []
            for line in req.lines:
                code = (line.material_code or '').strip()
                material = Material.query.filter_by(code=code).first() if code else None
                if material is None:
                    material = _find_material_by_name_spec(line.name, line.spec)
                if material is None:
                    if req.auto_create_material:
                        name = (line.name or '').strip()
                        if not name:
                            unmatched.append(code or '(空)')
                            continue
                        unit = _resolve_material_unit(line.unit)
                        new_code = _generate_auto_material_code()
                        material = Material(
                            code=new_code,
                            name=name,
                            spec=(line.spec or '').strip() or None,
                            unit_id=unit.id if unit else None,
                            price=0,
                            stock=0,
                        )
                        db.session.add(material)
                        db.session.flush()
                        auto_created.append({'code': new_code, 'name': name})
                    else:
                        unmatched.append(code or '(空)')
                        continue
                price = round_to_2_decimals(
                    line.price if line.price is not None else (material.price or 0)
                )
                matched.append({
                    'material': material,
                    'quantity': round_to_2_decimals(line.quantity),
                    'price': price,
                })
            if unmatched:
                db.session.rollback()
                return api_json_error(
                    '以下物料未建档，无法生成入库草稿，请先建档或转人工处理：'
                    + '、'.join(dict.fromkeys(unmatched)),
                    400,
                )
            if not matched:
                db.session.rollback()
                return api_json_error('没有可生成草稿的有效物料行', 400)

            # 仓库必填：优先用传入值，否则自动带默认仓库
            warehouse_code = (req.warehouse_code or req.warehouse or '').strip()
            warehouse = None
            if warehouse_code:
                warehouse = Warehouse.query.filter(
                    (Warehouse.code == warehouse_code) | (Warehouse.name == warehouse_code)
                ).first()
                if warehouse is None:
                    return api_json_error(f'仓库不存在：{warehouse_code}', 400)
                if (warehouse.status or 'active') != 'active':
                    return api_json_error(f'仓库 [{warehouse.name}] 已停用', 403)
            else:
                warehouse = get_default_warehouse()
                if warehouse is None:
                    return api_json_error('请选择仓库', 400)

            # 库位管理开启且保存强制时，以仓库作为库位兜底
            if location_management_enabled() and location_required_on_save():
                if warehouse is None or not (warehouse.name or warehouse.code):
                    return api_json_error('启用库位管理后，入库草稿必须填写仓库/库位', 400)

            business_type = req.business_type
            if business_type == '采购入库' and purchase_in_order_requires_order():
                return api_json_error('系统要求采购入库必须关联采购订单，请从采购订单下推或选单生成', 403)

            order = InOrder(
                order_no=generate_order_no('IN'),
                date=date.today(),
                warehouse=warehouse.name if warehouse else None,
                business_type=business_type,
                purpose='移动端识别单据确认',
                remark=(req.remark or '')[:200] or '移动端拍照识别，经人工确认生成草稿',
                status='pending',
                operator_id=user.id,
                total_amount=0,
            )
            db.session.add(order)
            db.session.flush()
            total_amount = 0
            for row in matched:
                material = row['material']
                quantity = row['quantity']
                price = row['price']
                amount = round_to_2_decimals(quantity * price)
                total_amount += amount
                db.session.add(InOrderItem(
                    in_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    price=price,
                    amount=amount,
                    remark='移动端识别，经人工确认',
                ))
            order.total_amount = round_to_2_decimals(total_amount)
            db.session.commit()
            msg = '入库草稿已生成'
            if auto_created:
                msg += f'，同时自动建档 {len(auto_created)} 个物料'
            return api_json_success({
                'order_no': order.order_no,
                'status': 'pending',
                'auto_created': auto_created,
                'items': [
                    {'code': row['material'].code, 'name': row['material'].name,
                     'quantity': row['quantity']}
                    for row in matched
                ],
            }, msg)
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            app.logger.exception('Mobile inbound draft failed')
            return api_json_error('入库草稿生成失败', 500)

    # pydantic:reason=新增移动端语音建单端点，按 A8 要求使用 pydantic 输入校验
    @app.route('/api/mobile/voice_out_draft', methods=['POST'])
    @csrf.exempt
    @api_role_required('warehouse')
    @mobile_api_idempotent('voice_out_draft')
    def native_api_voice_out_draft(user):
        """手机端语音建单：说「领8*25螺丝 1000个」→ 生成领料单草稿（status=pending）。

        两阶段协议（dry_run）：
          - dry_run=true  → 只解析+匹配，返回候选供用户点选（不建单）
          - dry_run=false → 用用户确认的物料+数量建草稿

        边界（AGENTS.md:20 / R5）：
          - 只建 pending 草稿，**不扣库存**；提交/完成仍由人工在出库页执行
          - 多命中/低置信度必须回退人工选择，不擅自替用户决定
          - 全失败时明确告知"听成了什么 + 试过哪些策略"，不编造
        """
        from datetime import date
        from pydantic import BaseModel, Field
        from app import (Material, OutOrder, OutOrderItem, Warehouse,
                         api_json_error, api_json_success, generate_order_no,
                         get_default_warehouse, location_management_enabled,
                         location_required_on_save, round_to_2_decimals)

        # AI-VOICE-OUT-F01 / AI_PERMISSION_MATRIX.md「维护要求 1」：
        # 语音建单是按能力键 voice_out_draft 注册的 AI 草稿能力，必须经能力矩阵校验，
        # 不能只依赖 @api_role_required('warehouse')。这样能力可被
        # AI_PERMISSION_MATRIX / rollout 灰度 / 总开关统一治理，权限收口在服务端。
        #
        # 注意：这里**不能**用「AI 能力总校验」那个读 current_user 的函数——它依赖
        # Flask-Login 的 current_user，而本端点走 @api_role_required 的 Bearer Token
        # 通道（get_bearer_user() 不会写 current_user），一定拿到 AnonymousUser 而误拒。
        # 正确做法是用已解析出的 user 直接问角色矩阵，并叠加灰度/总开关/草稿开关。
        from app import (AI_CAPABILITY_BUSINESS_ENDPOINTS, _ai_feature_enabled,
                         _ai_global_enabled, _ai_permission_denied_text,
                         _ai_rollout_mode)
        from ai.ops.rollout_control import evaluate_rollout_access
        from ai.tools.registry import get_ai_tool_spec
        from app.ai.policies import is_ai_capability_allowed_for_role

        _voice_cap = 'voice_out_draft'
        _voice_spec = get_ai_tool_spec(_voice_cap)
        _biz_view = app.view_functions.get(
            AI_CAPABILITY_BUSINESS_ENDPOINTS.get(_voice_cap, '')
        )
        _biz_roles = getattr(_biz_view, '_required_roles', None) if _biz_view else None
        _voice_decision = evaluate_rollout_access(
            capability=_voice_cap,
            role=user.role,
            user_id=user.id,
            risk_level=(_voice_spec.risk_level if _voice_spec else 'draft'),
            mode=_ai_rollout_mode(),
            allowed_user_ids=None,
            global_enabled=_ai_global_enabled(),
        )
        if not (_voice_spec
                and is_ai_capability_allowed_for_role(
                    _voice_cap, user.role, business_roles=_biz_roles)
                and _voice_decision.allowed
                and _ai_feature_enabled('ai_feature_drafts_enabled', True)):
            return api_json_error(
                _ai_permission_denied_text(_voice_cap), 403
            )

        class VoiceOutDraftRequest(BaseModel):
            text: str = Field(min_length=1, max_length=500)
            warehouse: str | None = None
            warehouse_code: str | None = None
            picker: str | None = None
            # true=只解析匹配（消歧用）；false=建草稿
            dry_run: bool = True
            # 消歧后用户选定的物料编码/数量（dry_run=false 时必填）
            material_code: str | None = None
            quantity: float | None = None

        payload = request.get_json(silent=True) or {}
        try:
            req = VoiceOutDraftRequest.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - pydantic 校验错误统一转 400
            return api_json_error(f'参数校验失败：{exc}', 400)

        # 仓库必填（未传时默认仓库兜底）
        warehouse_code = (req.warehouse_code or req.warehouse or '').strip()
        warehouse = None
        if warehouse_code:
            warehouse = Warehouse.query.filter(
                (Warehouse.code == warehouse_code) | (Warehouse.name == warehouse_code)
            ).first()
            if warehouse is None:
                return api_json_error(f'仓库不存在：{warehouse_code}', 400)
            if (warehouse.status or 'active') != 'active':
                return api_json_error(f'仓库 [{warehouse.name}] 已停用', 403)
        else:
            warehouse = get_default_warehouse()
            if warehouse is None:
                return api_json_error('请选择仓库', 400)

        # ① 解析语音文本 → 关键词/数量/规格
        parsed = _parse_voice_out_text(req.text)
        keyword = parsed['keyword']
        spec_hint = parsed['spec_hint']

        if not keyword and not spec_hint:
            # 听不出任何物料信息（如只说「领料」）——导航意图，不是建单
            return api_json_error(
                '没听到物料信息。请说「领8*25螺丝 1000个」这样的完整指令', 400
            )

        # ② 解析物料：优先用用户已确认的编码（第二阶段），否则走六层降级匹配
        if not req.dry_run and req.material_code:
            chosen = Material.query.filter_by(code=req.material_code.strip()).first()
            if chosen is None:
                return api_json_error(f'物料不存在：{req.material_code}', 400)
            matches_payload = [{'material': chosen, 'score': 100, 'strategy': 'user_choice'}]
            match_result = {
                'status': 'success', 'material': chosen,
                'matches': matches_payload, 'root': parsed['keyword'],
                'spec': spec_hint, 'strategies_tried': ['user_choice'],
            }
        else:
            match_result = _match_voice_material(keyword, spec_hint, warehouse)

        # 数量：用户确认值优先，其次语音解析值；都没有则 None（人工填，不猜）
        quantity = req.quantity if req.quantity is not None else parsed['quantity']

        def _match_to_json(item):
            material = item['material']
            return {
                'material_id': material.id,
                'code': material.code,
                'name': material.name or '',
                'spec': material.spec or '',
                'unit': material.unit.name if material.unit else '',
                'category': material.category.name if material.category else '',
                'price': round_to_2_decimals(material.price or 0),
                'score': item['score'],
                'strategy': item['strategy'],
            }

        # ③ dry_run：只返回解析+匹配结果，供客户端消歧
        if req.dry_run:
            return api_json_success({
                'stage': 'preview',
                'heard_text': parsed['raw'],
                'normalized_text': parsed['normalized'],
                'keyword': keyword,
                'root': match_result['root'],
                'spec': spec_hint,
                'quantity': quantity,
                'unit': parsed['unit'],
                'match_status': match_result['status'],
                'matches': [_match_to_json(m) for m in match_result['matches']],
                'strategies_tried': match_result['strategies_tried'],
                'warehouse': warehouse.name if warehouse else '',
                'warehouse_code': warehouse.code if warehouse else '',
                # 降级说明：让客户端能告诉用户"我做了什么努力"（R5 不编造）
                'degraded': match_result['status'] != 'success',
            }, '解析完成' if match_result['status'] == 'success'
               else '请选择物料' if match_result['status'] == 'multiple'
               else '未找到匹配物料')

        # ④ 建草稿：必须是唯一确定的物料（多命中不允许擅自建单）
        material = match_result['material']
        if material is None:
            return api_json_error(
                '未能确定物料，请先选择具体物料后再生成草稿', 400
            )
        if quantity is None or quantity <= 0:
            return api_json_error(
                '未识别到数量，请补充数量后再生成草稿（如「领8*25螺丝 1000个」）', 400
            )

        # 库位：开库位管理且强制时，以仓库名兜底（与 scan_batch_draft 一致）
        location = (warehouse.name or '').strip()
        if location_management_enabled() and location_required_on_save() and not location:
            return api_json_error('启用库位管理后，出库草稿必须填写仓库/库位', 400)

        try:
            qty = round_to_2_decimals(quantity)
            price = round_to_2_decimals(material.price or 0)
            order = OutOrder(
                order_no=generate_order_no('OU'),
                date=date.today(),
                business_type='领料单',
                warehouse=warehouse.name,
                location=location,
                purpose='语音建单（待确认）',
                remark=(f'语音建单：{parsed["raw"]}'[:200]),
                picker=(req.picker or '').strip()[:50] or None,
                status='pending',  # 草稿：人工确认后才 deduct_stock
                operator_id=user.id,
            )
            db.session.add(order)
            db.session.flush()
            db.session.add(OutOrderItem(
                out_order_id=order.id,
                material_id=material.id,
                quantity=qty,
                price=price,
                amount=round_to_2_decimals(qty * price),
            ))
            order.total_amount = sum(item.amount or 0 for item in order.items)
            db.session.commit()

            return api_json_success({
                'stage': 'created',
                'order_id': order.id,
                'order_no': order.order_no,
                'status': order.status,
                'warehouse': order.warehouse,
                'picker': order.picker or '',
                'heard_text': parsed['raw'],
                'items': [{
                    'material_id': material.id,
                    'code': material.code,
                    'name': material.name or '',
                    'spec': material.spec or '',
                    'unit': material.unit.name if material.unit else '',
                    'quantity': qty,
                }],
            }, f'已生成待确认草稿：{order.order_no}')
        except Exception:  # noqa: BLE001
            db.session.rollback()
            app.logger.exception('Mobile voice out draft failed')
            return api_json_error('语音建单草稿生成失败，请稍后重试', 500)

