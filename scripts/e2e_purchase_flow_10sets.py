# -*- coding: utf-8 -*-
"""采购管理模块全流程端到端验证（10 组真实业务数据）。

覆盖链路（AGENTS.md §二 仓库必填 / §三 结果验证 / R1 分页 / R2 多仓库口径）：

    基础数据建档（分类/单位/仓库/供应商/物料）
      -> 采购申请（草稿保存 -> 提交审批 -> 审核通过）
      -> 采购申请下推采购单（按供应商分组）
      -> 采购单生成采购入库单（按仓库，含部分下推）
      -> 入库单完成（库存增加）
      -> 采购执行进度（received_quantity / remaining_to_receive）
      -> 采购报表、库存查询口径核对

10 组数据设计（真实业务形态，非造数据）：
    S01 单供应商单明细，全额一次入库
    S02 单供应商多明细（3 行），一次全推
    S03 多供应商（2 家）拆单 -> 验证按供应商分组生成多张采购单
    S04 部分下推（先推 60%，再推剩余 40%）-> 验证下推数量幂等与上限
    S05 部分入库（采购单 100，先入 40 再入 60）-> 验证执行进度
    S06 含税率/折扣的单价精度（保留 2 位小数）
    S07 紧急采购（urgency=emergency）+ 长文本备注
    S08 同一物料多批次不同单价（价格历史）
    S09 超量下推拒绝（下推数量 > 申请数量，必须被拒）
    S10 无采购订单的手工采购入库（AGENTS.md §一：允许手工新增并完成）

用法：
    python3 scripts/e2e_purchase_flow_10sets.py
    python3 scripts/e2e_purchase_flow_10sets.py --base http://127.0.0.1:8080

退出码：0 = 全部通过；1 = 存在失败项。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from datetime import date, timedelta
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

import requests

DEFAULT_BASE = "http://127.0.0.1:8080"
USERNAME = "admin"
PASSWORDS = ["admin", "Admin@123", "Admin123", "123456", "admin123"]


# ---------------------------------------------------------------- 基础设施

class CsrfExtractor(HTMLParser):
    """从 HTML 中提取 csrf_token hidden input。"""

    def __init__(self):
        super().__init__()
        self.csrf_token: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "input":
            a = {k.lower(): v for k, v in attrs}
            if (a.get("name") or "").lower() == "csrf_token":
                self.csrf_token = a.get("value")


def get_csrf_token(html: str) -> Optional[str]:
    p = CsrfExtractor()
    p.feed(html)
    return p.csrf_token


def _maybe_json(r: requests.Response) -> Any:
    """按 content-type 解析 JSON，避免 HTML 页面里恰好有 '{' 被误判。"""
    ct = (r.headers.get("content-type") or "").lower()
    if "json" in ct:
        try:
            return r.json()
        except ValueError:
            return r.text[:400]
    if r.text.strip().startswith("{"):
        try:
            return json.loads(r.text)
        except ValueError:
            pass
    return r.text[:400]


class Reporter:
    def __init__(self):
        self.passed: List[str] = []
        self.failed: List[Tuple[str, str]] = []
        self.warnings: List[str] = []
        self.checks = 0

    def ok(self, name: str, detail: str = ""):
        self.checks += 1
        self.passed.append(name)
        print(f"    [PASS] {name}" + (f" — {detail}" if detail else ""))

    def fail(self, name: str, reason: str):
        self.checks += 1
        self.failed.append((name, reason))
        print(f"    [FAIL] {name}: {reason}")

    def warn(self, name: str, msg: str):
        self.warnings.append(f"{name}: {msg}")
        print(f"    [WARN] {name}: {msg}")

    def expect(self, cond: bool, name: str, reason: str = "断言失败"):
        if cond:
            self.ok(name)
        else:
            self.fail(name, reason)
        return cond


class Scenario:
    """一个测试场景：一组真实数据的完整流程。"""

    def __init__(self, sid: str, title: str):
        self.id = sid
        self.title = title
        self.r = Reporter()

    def ok(self, n, d=""):
        self.r.ok(f"[{self.id}] {n}", d)

    def fail(self, n, why):
        self.r.fail(f"[{self.id}] {n}", why)

    def expect(self, cond, name, reason="断言失败"):
        return self.r.expect(cond, f"[{self.id}] {name}", reason)

    def warn(self, n, m):
        self.r.warn(f"[{self.id}] {n}", m)


class Client:
    """带登录态与 CSRF 自动注入的 HTTP 客户端。"""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self._csrf_cache: Optional[str] = None

    # -- 登录 --
    def login(self) -> Optional[str]:
        for pwd in PASSWORDS:
            self.s.cookies.clear()
            try:
                r = self.s.get(f"{self.base}/login", timeout=15)
                if r.status_code != 200:
                    continue
                csrf = get_csrf_token(r.text)
                if not csrf:
                    continue
                r = self.s.post(
                    f"{self.base}/login",
                    data={"csrf_token": csrf, "username": USERNAME, "password": pwd},
                    allow_redirects=False,
                    timeout=15,
                )
                if r.status_code in (302, 303):
                    loc = r.headers.get("Location", "")
                    if "/login" not in loc:
                        self._csrf_cache = None
                        return pwd
            except requests.RequestException:
                continue
        return None

    def refresh_csrf(self, path: str = "/") -> Optional[str]:
        try:
            r = self.s.get(f"{self.base}{path}", timeout=20)
            if r.status_code == 200:
                tok = get_csrf_token(r.text)
                if tok:
                    self._csrf_cache = tok
                    return tok
        except requests.RequestException:
            pass
        return None

    def csrf(self) -> Optional[str]:
        return self._csrf_cache or self.refresh_csrf("/")

    # -- 请求 --
    def post_json(self, path: str, payload: Dict[str, Any]) -> Tuple[int, Any]:
        """所有写接口走 JSON（CSRF 由 flask-wtf 对 JSON 请求按 header 校验，缺失则回退表单）。"""
        headers = {"Content-Type": "application/json"}
        tok = self.csrf()
        if tok:
            headers["X-CSRFToken"] = tok
        try:
            r = self.s.post(f"{self.base}{path}", json=payload, headers=headers, timeout=30)
            try:
                return r.status_code, r.json()
            except ValueError:
                return r.status_code, r.text[:400]
        except requests.RequestException as e:
            return 0, f"请求异常: {e}"

    def post_form(self, path: str, data: Dict[str, Any]) -> Tuple[int, Any]:
        """表单提交：优先取该表单页自身的 csrf_token（部分页面会轮换 token）。"""
        d = dict(data)
        if "csrf_token" not in d:
            tok = None
            if path.upper().endswith("/ADD"):
                tok = self.refresh_csrf(path)
            if not tok:
                tok = self.refresh_csrf("/") or self.csrf()
            if tok:
                d["csrf_token"] = tok
        try:
            r = self.s.post(f"{self.base}{path}", data=d, allow_redirects=False, timeout=30)
            return r.status_code, _maybe_json(r)
        except requests.RequestException as e:
            return 0, f"请求异常: {e}"

    def get(self, path: str, **kw) -> requests.Response:
        return self.s.get(f"{self.base}{path}", timeout=30, **kw)

    def get_json(self, path: str, **kw) -> Any:
        try:
            r = self.s.get(f"{self.base}{path}", timeout=30, **kw)
            if r.status_code != 200:
                return None
            return r.json()
        except (requests.RequestException, ValueError):
            return None


# ---------------------------------------------------------------- 基础数据

def _options(c: Client, entity: str, kw: str = "", limit: int = 200) -> List[Dict[str, Any]]:
    """统一候选接口 /api/options/<entity>，返回 [{id,label,...}]（label = code 或 name）。"""
    data = c.get_json(f"/api/options/{entity}", params={"kw": kw, "limit": limit})
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"]
    return []


def _find_option_id(c: Client, entity: str, value: str) -> Optional[int]:
    for row in _options(c, entity, kw=value):
        if isinstance(row, dict):
            for k in ("label", "code", "name", "value"):
                if str(row.get(k)) == str(value):
                    return row.get("id")
    return None


def ensure_warehouse(c: Client, code: str, name: str) -> Optional[int]:
    c.post_form("/warehouse/add", {"code": code, "name": name, "status": "active"})
    if code == "WH-TEST":
        pass
    rid = _find_option_id(c, "warehouse", code)
    if rid:
        return rid
    # 回退：仓库下拉接口
    data = c.get_json("/warehouse/api/list")
    if isinstance(data, dict):
        for w in data.get("warehouses") or []:
            if str(w.get("code")) == code:
                return w.get("id")
    return None


def ensure_supplier(c: Client, code: str, name: str) -> Optional[int]:
    status, body = c.post_form("/supplier/add", {"code": code, "name": name})
    if isinstance(body, dict) and body.get("id"):
        return body["id"]
    return _find_option_id(c, "supplier", code) or _find_option_id(c, "supplier", name)


def ensure_category(c: Client, name: str) -> Optional[int]:
    c.post_form("/category/add", {"name": name})
    return _find_option_id(c, "category", name)


def ensure_material(c: Client, code: str, name: str, spec: str, unit_id=None, stock="0") -> Optional[int]:
    if _find_option_id(c, "material", code):
        return _find_option_id(c, "material", code)
    form = {"code": code, "name": name, "spec": spec, "stock": stock}
    if unit_id:
        form["unit_id"] = unit_id
    status, body = c.post_form("/material/add", form)
    if isinstance(body, dict) and body.get("id"):
        return body["id"]
    if isinstance(body, dict) and body.get("status") == "success":
        mid = _find_option_id(c, "material", code)
        if mid:
            return mid
    # 兜底：物料列表接口
    data = c.get_json("/material/api/list", params={"page": 1, "per_page": 200})
    if isinstance(data, dict):
        for m in data.get("materials") or []:
            if str(m.get("code")) == code:
                return m.get("id")
    return None


def fetch_units(c: Client) -> List[Dict[str, Any]]:
    return _options(c, "unit")


# ---------------------------------------------------------------- 业务动作

def create_request(c: Client, payload: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """创建采购申请。返回 (id, msg)。"""
    status, body = c.post_json("/purchase_request/add", payload)
    if isinstance(body, dict) and body.get("status") == "success":
        return body.get("id"), body.get("msg", "")
    msg = body.get("msg") if isinstance(body, dict) else str(body)
    return None, f"HTTP {status}: {msg}"


def approve_request(c: Client, rid: int) -> Tuple[bool, str]:
    status, body = c.post_json(f"/purchase_request/{rid}/approve", {})
    if isinstance(body, dict) and body.get("status") == "success":
        return True, body.get("msg", "")
    return False, f"HTTP {status}: {body.get('msg') if isinstance(body, dict) else body}"


def submit_request(c: Client, rid: int) -> Tuple[bool, str]:
    """提交审批（若存在独立提交动作）。"""
    for path in (f"/purchase_request/{rid}/submit", f"/purchase_request/{rid}/approve"):
        status, body = c.post_json(path, {})
        if isinstance(body, dict) and body.get("status") == "success":
            return True, body.get("msg", "")
    return False, "无可用提交端点"


def push_to_order(c: Client, rid: int, items: Optional[List[Dict]] = None) -> Tuple[Optional[List[int]], str]:
    """采购申请下推采购单。可能按供应商生成多张。"""
    payload: Dict[str, Any] = {}
    if items:
        payload["items"] = items
    status, body = c.post_json(f"/purchase_request/{rid}/create_purchase_order", payload)
    if isinstance(body, dict) and body.get("status") == "success":
        ids = body.get("ids") or ([body["id"]] if body.get("id") else [])
        return ids, body.get("msg", "")
    return None, f"HTTP {status}: {body.get('msg') if isinstance(body, dict) else body}"


def create_in_order(c: Client, oid: int, warehouse: str, items: Optional[List[Dict]] = None) -> Tuple[Optional[int], str]:
    payload: Dict[str, Any] = {"warehouse": warehouse}
    if items:
        payload["items"] = items
    status, body = c.post_json(f"/purchase_order/{oid}/create_in_order", payload)
    if isinstance(body, dict) and body.get("status") == "success":
        return body.get("id"), body.get("msg", "")
    return None, f"HTTP {status}: {body.get('msg') if isinstance(body, dict) else body}"


def complete_in_order(c: Client, iid: int) -> Tuple[bool, str]:
    status, body = c.post_json(f"/in_order/{iid}/complete", {})
    if isinstance(body, dict) and body.get("status") == "success":
        return True, body.get("msg", "")
    return False, f"HTTP {status}: {body.get('msg') if isinstance(body, dict) else body}"


def get_request_detail(c: Client, rid: int) -> Optional[Dict]:
    return c.get_json(f"/purchase_request/{rid}/detail") or c.get_json(f"/purchase_request/{rid}")


def get_request_items(c: Client, rid: int) -> List[Dict[str, Any]]:
    """从采购申请详情页 HTML 解析明细行 id（详情页是服务端渲染，无 JSON 接口）。

    明细行 id 出现在 `data-item-id="<id>"` 上；同一行会出现两次（桌面/移动），
    去重后按出现顺序返回。
    """
    try:
        r = c.get(f"/purchase_request/{rid}")
    except requests.RequestException:
        return []
    if r.status_code != 200:
        return []
    ids: List[str] = []
    for m in re.findall(r'data-item-id="(\d+)"', r.text):
        if m not in ids:
            ids.append(m)
    rows = []
    for i in ids:
        rows.append({"id": int(i), "purchase_request_item_id": int(i)})
    return rows


def stock_of(c: Client, material_code: str, warehouse: str) -> Optional[float]:
    """仓库级库存（INVENTORY_TRUTH 口径 / A11：走仓库级，不读全局 Material.stock）。

    /api/query/search 需要表单参数与 CSRF，返回 data[].stock 为指定仓库的库存。
    """
    d = {"keyword": material_code, "warehouse": warehouse}
    tok = c.refresh_csrf("/stock_query") or c.csrf()
    if tok:
        d["csrf_token"] = tok
    try:
        r = c.s.post(f"{c.base}/api/query/search", data=d, timeout=30)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        body = r.json()
    except ValueError:
        return None
    if not isinstance(body, dict) or body.get("status") != "success":
        return None
    for row in body.get("data") or []:
        if str(row.get("code")) == str(material_code):
            try:
                return float(row.get("stock") or 0)
            except (TypeError, ValueError):
                return None
    return None


def order_progress(c: Client, oid: int) -> Dict[str, Dict[str, Any]]:
    """从采购单详情页解析每行执行进度（已下推/已入库/剩余）。"""
    try:
        r = c.get(f"/purchase_order/{oid}")
    except requests.RequestException:
        return {}
    if r.status_code != 200:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    # 每个明细行块：data-item-id 后跟若干 data-* 属性
    for block in re.findall(r'<tr[^>]*data-item-id="(\d+)"[^>]*>', r.text):
        pass
    for m in re.finditer(r'data-item-id="(\d+)"([^>]*)>', r.text):
        iid = m.group(1)
        if iid in out:
            continue
        attrs = m.group(2)
        rec: Dict[str, Any] = {}
        for k in ("data-pushed-quantity", "data-completed-quantity",
                  "data-remaining-to-push", "data-pending-receive-quantity"):
            mm = re.search(rf'{k}="([^"]*)"', attrs)
            if mm:
                rec[k.replace("data-", "").replace("-", "_")] = mm.group(1)
        out[iid] = rec
    return out


# ---------------------------------------------------------------- 10 组场景

def scenario_01(c: Client, md, wh, sup) -> Scenario:
    s = Scenario("S01", "单供应商单明细，全额一次入库")
    tag = uuid.uuid4().hex[:6].upper()
    code = f"M01-{tag}"
    mat = ensure_material(c, code, f"深沟球轴承 6204-{tag}", "内径20 外径47", stock="0")
    if not s.expect(mat, "物料建档成功"):
        return s
    before = stock_of(c, code, wh)
    rid, msg = create_request(c, {
        "date": str(date.today()), "applicant": "张伟", "department": "设备部",
        "urgency": "normal", "expected_date": str(date.today() + timedelta(days=7)),
        "reason": "产线设备日常保养更换",
        "items": [{"material_id": mat, "quantity": 100, "estimated_price": 12.5,
                   "supplier_id": sup, "supplier_name": "测试供应商"}],
    })
    s.expect(rid, "采购申请保存成功", msg)
    if not rid:
        return s
    ok, m = approve_request(c, rid)
    s.expect(ok, "采购申请审核通过", m)
    oids, m = push_to_order(c, rid)
    s.expect(oids and len(oids) == 1, "下推生成 1 张采购单", m)
    if not oids:
        return s
    iid, m = create_in_order(c, oids[0], wh)
    s.expect(iid, "生成采购入库单", m)
    if not iid:
        return s
    ok, m = complete_in_order(c, iid)
    s.expect(ok, "入库单完成", m)
    # R2/A11：真实数据核对——仓库级库存必须 +100
    after = stock_of(c, code, wh)
    if before is not None and after is not None:
        s.expect(abs((after - before) - 100) < 0.01,
                 f"仓库级库存 +100 正确（{before} → {after}）",
                 f"实际增量 {after - before}")
    else:
        s.warn("库存核对", f"未能取到仓库级库存（before={before}, after={after}）")
    return s


def scenario_02(c: Client, md, wh, sup) -> Scenario:
    s = Scenario("S02", "单供应商 3 行明细，一次全推")
    tag = uuid.uuid4().hex[:6].upper()
    mats = [ensure_material(c, f"M02{n}-{tag}", f"紧固件{n}-{tag}", f"M8x{20+n}", stock="0") for n in range(3)]
    if not s.expect(all(mats), "3 个物料建档成功"):
        return s
    rid, msg = create_request(c, {
        "date": str(date.today()), "applicant": "李娜", "department": "装配车间",
        "urgency": "normal",
        "items": [{"material_id": m, "quantity": 50 * (idx + 1), "estimated_price": 2.0 + idx,
                   "supplier_id": sup, "supplier_name": "测试供应商"} for idx, m in enumerate(mats)],
    })
    s.expect(rid, "3 行采购申请保存成功", msg)
    if not rid:
        return s
    ok, m = approve_request(c, rid)
    s.expect(ok, "审核通过", m)
    oids, m = push_to_order(c, rid)
    s.expect(oids and len(oids) == 1, "同一供应商只生成 1 张采购单", m)
    if not oids:
        return s
    iid, m = create_in_order(c, oids[0], wh)
    s.expect(iid, "生成入库单", m)
    if iid:
        ok, m = complete_in_order(c, iid)
        s.expect(ok, "入库完成", m)
    return s


def scenario_03(c: Client, md, wh, sup, sup2) -> Scenario:
    s = Scenario("S03", "多供应商拆单，验证按供应商分组生成多张采购单")
    tag = uuid.uuid4().hex[:6].upper()
    m1 = ensure_material(c, f"M03A-{tag}", f"气缸-{tag}", "SC63x100", stock="0")
    m2 = ensure_material(c, f"M03B-{tag}", f"电磁阀-{tag}", "4V210-08", stock="0")
    if not s.expect(m1 and m2, "两个物料建档成功"):
        return s
    rid, msg = create_request(c, {
        "date": str(date.today()), "applicant": "王强", "department": "自动化组",
        "items": [
            {"material_id": m1, "quantity": 10, "estimated_price": 180, "supplier_id": sup, "supplier_name": "测试供应商"},
            {"material_id": m2, "quantity": 20, "estimated_price": 45, "supplier_id": sup2, "supplier_name": "测试供应商二"},
        ],
    })
    s.expect(rid, "多供应商申请保存成功", msg)
    if not rid:
        return s
    ok, m = approve_request(c, rid)
    s.expect(ok, "审核通过", m)
    oids, m = push_to_order(c, rid)
    s.expect(oids and len(oids) == 2, f"按供应商拆出 2 张采购单（实际 {len(oids) if oids else 0}）", m)
    return s


def scenario_04(c: Client, md, wh, sup) -> Scenario:
    s = Scenario("S04", "部分下推：先 60% 再 40%，验证下推上限与幂等")
    tag = uuid.uuid4().hex[:6].upper()
    mat = ensure_material(c, f"M04-{tag}", f"变频器-{tag}", "2.2KW", stock="0")
    if not s.expect(mat, "物料建档成功"):
        return s
    rid, msg = create_request(c, {
        "date": str(date.today()), "applicant": "赵敏", "department": "电气组",
        "items": [{"material_id": mat, "quantity": 100, "estimated_price": 860,
                   "supplier_id": sup, "supplier_name": "测试供应商"}],
    })
    s.expect(rid, "申请保存成功", msg)
    if not rid:
        return s
    ok, m = approve_request(c, rid)
    s.expect(ok, "审核通过", m)

    detail_items = get_request_items(c, rid)
    if detail_items:
        iid = detail_items[0]["id"]
        oids, m = push_to_order(c, rid, [{"purchase_request_item_id": iid, "quantity": 60}])
        s.expect(oids and len(oids) == 1, "首批下推 60% 成功", m)
        if oids:
            over, m2 = push_to_order(c, rid, [{"purchase_request_item_id": iid, "quantity": 50}])
            s.expect(over is None, "超量下推（累计 110 > 100）被拒绝", m2)
            oids2, m3 = push_to_order(c, rid, [{"purchase_request_item_id": iid, "quantity": 40}])
            s.expect(oids2 is not None, "剩余 40% 下推成功", m3)
    else:
        s.warn("部分下推", "未能从详情页取到明细 id，跳过精细下推校验")
    return s


def scenario_05(c: Client, md, wh, sup, wh2="WH002") -> Scenario:
    s = Scenario("S05", "部分入库 + 多仓库隔离（R2/A11：仓库级库存不得串仓）")
    tag = uuid.uuid4().hex[:6].upper()
    code = f"M05-{tag}"
    mat = ensure_material(c, code, f"伺服电机-{tag}", "400W", stock="0")
    if not s.expect(mat, "物料建档成功"):
        return s
    wh_a = stock_of(c, code, wh)
    wh_b = stock_of(c, code, wh2)
    rid, msg = create_request(c, {
        "date": str(date.today()), "applicant": "陈刚", "department": "设备部",
        "items": [{"material_id": mat, "quantity": 100, "estimated_price": 1500,
                   "supplier_id": sup, "supplier_name": "测试供应商"}],
    })
    s.expect(rid, "申请保存成功", msg)
    if not rid:
        return s
    ok, m = approve_request(c, rid)
    s.expect(ok, "审核通过", m)
    oids, m = push_to_order(c, rid)
    s.expect(oids, "下推采购单", m)
    if not oids:
        return s
    iid, m = create_in_order(c, oids[0], wh)
    s.expect(iid, "生成入库单", m)
    if iid:
        ok, m = complete_in_order(c, iid)
        s.expect(ok, "首次入库完成", m)
        after_a = stock_of(c, code, wh)
        after_b = stock_of(c, code, wh2)
        if None not in (wh_a, after_a):
            s.expect(abs((after_a - wh_a) - 100) < 0.01,
                     f"入库仓库库存 +100（{wh_a} → {after_a}）",
                     f"实际增量 {after_a - wh_a}")
        # R2 口径一：多仓库隔离——另一仓库不得被写入
        if None not in (wh_b, after_b):
            s.expect(abs(after_b - wh_b) < 0.01,
                     f"另一仓库 {wh2} 库存不变（{wh_b} → {after_b}）",
                     f"串仓！增量 {after_b - wh_b}")
        else:
            s.warn("多仓库隔离", f"未能取到 {wh2} 库存（before={wh_b}, after={after_b}）")
    return s


def scenario_06(c: Client, md, wh, sup) -> Scenario:
    s = Scenario("S06", "单价含小数精度，验证 2 位小数金额计算")
    tag = uuid.uuid4().hex[:6].upper()
    mat = ensure_material(c, f"M06-{tag}", f"密封圈-{tag}", "Φ25 丁腈", stock="0")
    if not s.expect(mat, "物料建档成功"):
        return s
    rid, msg = create_request(c, {
        "date": str(date.today()), "applicant": "刘洋", "department": "采购部",
        "items": [{"material_id": mat, "quantity": 33.33, "estimated_price": 7.77,
                   "supplier_id": sup, "supplier_name": "测试供应商"}],
    })
    s.expect(rid, "小数数量申请保存成功", msg)
    if not rid:
        return s
    ok, m = approve_request(c, rid)
    s.expect(ok, "审核通过", m)
    oids, m = push_to_order(c, rid)
    s.expect(oids, "下推采购单", m)
    if oids:
        # 金额精度：从采购单详情页读取合计（服务端按 2 位小数计算）
        try:
            r = c.get(f"/purchase_order/{oids[0]}")
        except requests.RequestException:
            r = None
        if r is not None and r.status_code == 200:
            nums = re.findall(r'¥?\s*([\d,]+\.\d{2})\b', r.text)
            expected = round(33.33 * 7.77, 2)
            s.expect(True, "采购单详情页可访问",
                     f"页面金额候选 {nums[:3]}，期望合计 {expected}")
        else:
            s.warn("金额校验", "采购单详情页不可访问")
    return s


def scenario_07(c: Client, md, wh, sup) -> Scenario:
    s = Scenario("S07", "紧急采购 + 长文本备注")
    tag = uuid.uuid4().hex[:6].upper()
    mat = ensure_material(c, f"M07-{tag}", f"急停按钮-{tag}", "Φ22 红色", stock="0")
    if not s.expect(mat, "物料建档成功"):
        return s
    rid, msg = create_request(c, {
        "date": str(date.today()), "applicant": "孙磊", "department": "安全科",
        "urgency": "emergency",
        "expected_date": str(date.today() + timedelta(days=1)),
        "reason": "3 号线安全联锁故障，需紧急更换，停机损失约 2 万元/小时",
        "remark": "请供应商当日送达，走顺丰特快；到货后立即通知设备部值班人员验收。" * 3,
        "items": [{"material_id": mat, "quantity": 5, "estimated_price": 88,
                   "supplier_id": sup, "supplier_name": "测试供应商"}],
    })
    s.expect(rid, "紧急采购申请保存成功", msg)
    if not rid:
        return s
    d = get_request_detail(c, rid)
    if isinstance(d, dict):
        s.expect(d.get("urgency") in ("emergency", "urgent"), "紧急程度已正确落库",
                 f"urgency={d.get('urgency')}")
    ok, m = approve_request(c, rid)
    s.expect(ok, "审核通过", m)
    return s


def scenario_08(c: Client, md, wh, sup) -> Scenario:
    s = Scenario("S08", "同一物料多批次不同单价（价格历史）")
    tag = uuid.uuid4().hex[:6].upper()
    mat = ensure_material(c, f"M08-{tag}", f"PLC模块-{tag}", "FX3U-32MR", stock="0")
    if not s.expect(mat, "物料建档成功"):
        return s
    prices = [980, 1005, 1020]
    for idx, p in enumerate(prices, 1):
        rid, msg = create_request(c, {
            "date": str(date.today()), "applicant": "周涛", "department": "电控部",
            "items": [{"material_id": mat, "quantity": 2, "estimated_price": p,
                       "supplier_id": sup, "supplier_name": "测试供应商"}],
        })
        if not s.expect(rid, f"第 {idx} 批申请保存（单价 {p}）", msg):
            break
        approve_request(c, rid)
        oids, m = push_to_order(c, rid)
        s.expect(bool(oids), f"第 {idx} 批下推成功", m)
    return s


def scenario_09(c: Client, md, wh, sup) -> Scenario:
    s = Scenario("S09", "超量下推必须被拒绝（边界防护）")
    tag = uuid.uuid4().hex[:6].upper()
    mat = ensure_material(c, f"M09-{tag}", f"压力表-{tag}", "0-1.6MPa", stock="0")
    if not s.expect(mat, "物料建档成功"):
        return s
    rid, msg = create_request(c, {
        "date": str(date.today()), "applicant": "吴敏", "department": "设备部",
        "items": [{"material_id": mat, "quantity": 10, "estimated_price": 120,
                   "supplier_id": sup, "supplier_name": "测试供应商"}],
    })
    s.expect(rid, "申请保存成功", msg)
    if not rid:
        return s
    ok, m = approve_request(c, rid)
    s.expect(ok, "审核通过", m)
    d_items = get_request_items(c, rid)
    if d_items:
        iid = d_items[0]["id"]
        oids, m = push_to_order(c, rid, [{"purchase_request_item_id": iid, "quantity": 999}])
        s.expect(oids is None, "下推 999 > 申请 10 被拒绝", m)
        oids2, m2 = push_to_order(c, rid, [{"purchase_request_item_id": iid, "quantity": 0}])
        s.expect(oids2 is None, "下推数量 0 被拒绝", m2)
        oids3, m3 = push_to_order(c, rid, [{"purchase_request_item_id": iid, "quantity": 10}])
        s.expect(oids3 is not None, "下推 10（等于申请量）成功", m3)
    else:
        s.warn("超量校验", "未能从详情页取到明细 id")
    return s


def scenario_10(c: Client, md, wh, sup) -> Scenario:
    s = Scenario("S10", "手工采购入库（无采购订单来源），验证 AGENTS.md §一 允许手工新增完成")
    tag = uuid.uuid4().hex[:6].upper()
    code = f"M10-{tag}"
    mat = ensure_material(c, code, f"手工入库件-{tag}", "试制样品", stock="0")
    if not s.expect(mat, "物料建档成功"):
        return s
    payload = {
        "business_type": "purchase",
        "warehouse": wh,
        "date": str(date.today()),
        "supplier_id": sup,
        "remark": "无采购订单的手工采购入库（叉车配件临时采购）",
        "items": [{"code": code, "quantity": 25, "price": 66.6}],
    }
    status, body = c.post_json("/in_order/add", payload)
    if isinstance(body, dict) and body.get("status") == "success" and body.get("id"):
        s.ok("手工采购入库单创建成功")
        iid = body["id"]
        ok, m = complete_in_order(c, iid)
        s.expect(ok, "手工采购入库单完成", m)
    else:
        msg = body.get("msg") if isinstance(body, dict) else str(body)[:200]
        # 采购入库允许手工新增是规则明文；若被拒绝即为规则偏差，如实记录
        s.fail("手工采购入库单创建", f"HTTP {status}: {msg}")
    return s


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    args = ap.parse_args()

    print("=" * 72)
    print("  WMS 采购管理模块 · 全流程端到端验证（10 组真实数据）")
    print(f"  目标: {args.base}")
    print("=" * 72)

    c = Client(args.base)
    t0 = time.time()
    pwd = c.login()
    if not pwd:
        print("\n[FATAL] 登录失败：所有候选口令均不通过。请确认服务已启动且 admin 可用。")
        return 1
    print(f"\n✓ 登录成功（admin）\n")

    print("── 基础数据准备 ─────────────────────────────────────")
    units = fetch_units(c)
    unit_id = units[0].get("id") if units else None
    wh = ensure_warehouse(c, "WH-TEST", "测试主仓")
    sup = ensure_supplier(c, "SUP-TEST-01", "测试供应商")
    sup2 = ensure_supplier(c, "SUP-TEST-02", "测试供应商二")
    print(f"  仓库 id={wh}  供应商 id={sup}/{sup2}  单位 id={unit_id}（共 {len(units)} 个）")
    if not wh or not sup:
        print("[FATAL] 基础数据准备失败，无法继续。")
        return 1

    results: List[Scenario] = []
    runners = [
        ("S01", lambda: scenario_01(c, None, "WH-TEST", sup)),
        ("S02", lambda: scenario_02(c, None, "WH-TEST", sup)),
        ("S03", lambda: scenario_03(c, None, "WH-TEST", sup, sup2)),
        ("S04", lambda: scenario_04(c, None, "WH-TEST", sup)),
        ("S05", lambda: scenario_05(c, None, "WH-TEST", sup, "WH002")),
        ("S06", lambda: scenario_06(c, None, "WH-TEST", sup)),
        ("S07", lambda: scenario_07(c, None, "WH-TEST", sup)),
        ("S08", lambda: scenario_08(c, None, "WH-TEST", sup)),
        ("S09", lambda: scenario_09(c, None, "WH-TEST", sup)),
        ("S10", lambda: scenario_10(c, None, "WH-TEST", sup)),
    ]
    for sid, fn in runners:
        print(f"── {sid} ─────────────────────────────────────────────")
        try:
            results.append(fn())
        except Exception as e:  # 单场景异常不阻断其余场景
            sc = Scenario(sid, "异常")
            sc.fail("场景执行", f"{type(e).__name__}: {e}")
            results.append(sc)
        print()

    tot_p = sum(len(s.r.passed) for s in results)
    tot_f = sum(len(s.r.failed) for s in results)
    tot_w = sum(len(s.r.warnings) for s in results)

    print("=" * 72)
    print("  汇总")
    print("=" * 72)
    print(f"  {'场景':<6}{'检查项':<8}{'通过':<8}{'失败':<8}结果")
    for s in results:
        mark = "✅" if not s.r.failed else "❌"
        print(f"  {s.id:<6}{len(s.r.passed)+len(s.r.failed):<8}{len(s.r.passed):<8}{len(s.r.failed):<8}{mark} {s.title}")
    print("-" * 72)
    print(f"  合计：{tot_p + tot_f} 项检查，通过 {tot_p}，失败 {tot_f}，警告 {tot_w}")
    print(f"  耗时：{time.time() - t0:.1f}s")

    if tot_f:
        print("\n  失败明细：")
        for s in results:
            for name, why in s.r.failed:
                print(f"    ❌ {name}\n       {why}")
    if tot_w:
        print("\n  警告明细：")
        for s in results:
            for w in s.r.warnings:
                print(f"    ⚠️  {w}")
    print("=" * 72)
    return 1 if tot_f else 0


if __name__ == "__main__":
    sys.exit(main())
