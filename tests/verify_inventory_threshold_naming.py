# -*- coding: utf-8 -*-
"""库存阈值命名统一（AI-CI-GREEN-005）回归测试。

背景：`inventory_alert_enabled` 打开后，「安全库存」相关概念在系统里长期存在
**四种叫法**，容易在改动时写错字段、或在模板/接口间错位：

    数据库列            对外名称        出现位置
    min_stock           最低库存        界面、Excel、通知、报表
    max_stock           最大库存        （唯一，无歧义）
    reorder_point       **安全库存**    界面表单、Excel 表头、预警页
    safety_stock        （不是列！）    仅 API 响应 / Excel 导出 / 报表字典，
                                        值为 max(reorder_point, min_stock)

本测试锁定「对外统一叫法」，防止旧叫法回流：

T1. 一律不存在「最小库存」这个界面叫法（历史残留，已统一为「最低库存」）。
T2. 一律不存在「再订货点 / 再订购点」这个界面叫法（已统一为「安全库存」）；
    但在 Excel 表头**匹配**逻辑里必须保留为兼容别名，否则老模板导不进来。
T3. 两份物料导入模板（/material/download_template 与 /export/template/material）
    表头必须完全一致——它们是重复实现，任一漂移都会造成"两个入口模板不同"。
T4. 安全库存字段必须能正确往返：填「安全库存」→ 落 reorder_point；
    导出再导入后值不变（防止把 reorder_point 写进 min_stock 这类错位）。
T5. 界面文案与数据库列名的映射，必须在 Material 模型 docstring 里成文，
    避免下一个人重新猜。
T6. Python 侧不得出现「文案写安全库存、代码读 min_stock」的错位（AI-CI-GREEN-005-F01
    补）：上一轮只扫模板 + notifications.py，app.py 与 ai/** 全在盲区，正是本次
    错标能长期存活的根因。
T7. 「低于安全库存」只能出现在 danger 档（判定对象为 safety_stock 计算值）的标签行。
T8. Android 侧界面文案同样不得出现旧叫法（AI-CI-GREEN-005-F04 补）：T1/T2 只扫了
    模板 + notifications.py，Kotlin 是第二个盲区——「再订货点」这个叫法在手机端
    查库存结果卡上一直活着，正是同一根因（扫描集覆盖不全）的又一次漏网。
"""
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import db, Material, User  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


# ---------- T1/T2：源码级叫法扫描 ----------

# 只扫「会展示给用户」的位置：界面文案、通知正文、模板示例。
# 注释/兼容别名列表不算——那是有意保留的历史兼容。
TEMPLATE_DIR = APP_DIR / "templates"


def _user_facing_files():
    files = list(TEMPLATE_DIR.glob("*.html"))
    files.append(APP_DIR / "notifications.py")
    return files


def test_t1_no_legacy_min_stock_label():
    """T1：界面文案不得再出现「最小库存」（标准叫法是「最低库存」）。"""
    offenders = []
    for f in _user_facing_files():
        text = f.read_text(encoding="utf-8")
        if "最小库存" in text:
            offenders.append(f.name)
    assert not offenders, (
        f"以下文件仍在用旧叫法「最小库存」，应统一为「最低库存」：{offenders}"
    )


def test_t2_no_legacy_reorder_point_label_but_keep_alias():
    """T2：界面不再叫「再订货点」，但 Excel 表头匹配必须保留兼容别名。"""
    offenders = []
    for f in _user_facing_files():
        text = f.read_text(encoding="utf-8")
        if "再订货点" in text or "再订购点" in text:
            offenders.append(f.name)
    assert not offenders, (
        f"以下界面仍在用旧叫法「再订货点/再订购点」，应统一为「安全库存」：{offenders}"
    )
    # 兼容别名必须留在导入匹配逻辑里，否则老模板无法导入
    importer = (APP_DIR / "routes" / "material.py").read_text(encoding="utf-8")
    assert "再订货点" in importer and "再订购点" in importer, (
        "物料导入的表头匹配丢失了「再订货点/再订购点」兼容别名，"
        "会导致历史模板导入失败"
    )


def test_t3_two_material_templates_agree():
    """T3：两份物料导入模板的表头必须逐列一致。"""
    from openpyxl import load_workbook

    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        from werkzeug.security import generate_password_hash
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin",
            must_change_password=False,
        ))
        app_module.set_system_setting("inventory_alert_enabled", "1")
        db.session.commit()

    client = app_module.app.test_client()
    client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )

    urls = ["/material/download_template", "/export/template/material"]
    headers_seen = {}
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
        ws = load_workbook(io.BytesIO(resp.data)).active
        headers_seen[url] = [c.value for c in ws[1]]

    assert headers_seen[urls[0]] == headers_seen[urls[1]], (
        "两份物料导入模板表头不一致：\n"
        f"  {urls[0]}: {headers_seen[urls[0]]}\n"
        f"  {urls[1]}: {headers_seen[urls[1]]}\n"
        "两处是重复实现，必须同步。"
    )
    # 并且确实包含统一后的叫法
    assert "最低库存" in headers_seen[urls[0]], "模板缺少「最低库存」列"
    assert "安全库存" in headers_seen[urls[0]], "模板缺少「安全库存」列"


def test_t4_safety_stock_round_trip_and_column_mapping():
    """T4：安全库存填值 → 落 reorder_point；导出再导入值不变。"""
    from openpyxl import load_workbook, Workbook

    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        from werkzeug.security import generate_password_hash
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin",
                must_change_password=False,
            ))
        app_module.set_system_setting("inventory_alert_enabled", "1")
        db.session.commit()

    client = app_module.app.test_client()
    client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )

    # ① 表单提交：最低库存=7，安全库存=21
    resp = client.post(
        "/material/add",
        data={
            "code": "NAMING-RT-1", "name": "命名往返测试", "price": "3",
            "min_stock": "7", "max_stock": "200",
            "reorder_point": "21", "alert_days": "30",
        },
        content_type="application/x-www-form-urlencoded",
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302), f"/material/add -> {resp.status_code}"

    with app_module.app.app_context():
        m = Material.query.filter_by(code="NAMING-RT-1").first()
        assert m is not None, "物料未落库"
        assert m.min_stock == 7, f"最低库存应为 7，实际 {m.min_stock}"
        assert m.reorder_point == 21, (
            f"安全库存应落到 reorder_point=21，实际 {m.reorder_point}"
            "（若为 7，说明写进了 min_stock，字段错位）"
        )

    # ② 导出 → 再导入，值不得变化
    resp = client.get("/material/export")
    assert resp.status_code == 200, f"/material/export -> {resp.status_code}"
    wb = load_workbook(io.BytesIO(resp.data))
    ws = wb.active
    header = [c.value for c in ws[1]]
    assert "安全库存" in header, f"导出缺少「安全库存」列：{header}"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = client.post(
        "/material/import",
        data={"file": (buf, "roundtrip.xlsx")},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 302), f"/material/import -> {resp.status_code}"

    with app_module.app.app_context():
        m2 = Material.query.filter_by(code="NAMING-RT-1").first()
        assert m2 is not None, "回导后物料丢失"
        assert m2.min_stock == 7, f"回导后最低库存变了：{m2.min_stock}"
        assert m2.reorder_point == 21, f"回导后安全库存变了：{m2.reorder_point}"


def test_t5_naming_convention_is_documented():
    """T5：命名映射必须成文在 Material 模型 docstring 里。"""
    src = (APP_DIR / "models" / "master_data.py").read_text(encoding="utf-8")
    assert "库存阈值命名约定" in src, "Material 模型缺少「库存阈值命名约定」说明段"
    # 三个关键映射都要写到
    for token in ("min_stock", "reorder_point", "safety_stock"):
        assert token in src, f"命名约定说明缺少 {token}"
    assert "安全库存" in src, "命名约定说明未点明 reorder_point 对外叫「安全库存」"


# ---------- T6/T7：Python 侧「文案 ↔ 字段」错位扫描 ----------

# AI-CI-GREEN-005-F01：上一轮（AI-CI-GREEN-005）的 _user_facing_files() 只收了
# 模板和 notifications.py，app.py / ai/** 一个都没扫 —— 结果「文案写安全库存、
# 代码读 min_stock」的错位在这两个目录里活了很久。以下是两类共现特征的机械守卫。

T6_ALLOWLIST = {
    "models/master_data.py",       # 命名约定本体，必然同时提到两边的名字
    "routes/material.py",          # Excel 表头 + 导入兼容别名注释
    "routes/export.py",            # 同上
    "routes/inventory_alert.py",   # safety_stock 字段的校验/变更文案，属正确用法
}


def _py_source_files():
    """app/ 下全部 .py（排除 Android 工程与 __pycache__）。"""
    files = []
    for dirpath, dirnames, filenames in os.walk(APP_DIR):
        dirnames[:] = [
            d for d in dirnames
            if d not in ("android-native-wms", "__pycache__", "node_modules")
        ]
        for name in filenames:
            if name.endswith(".py"):
                files.append(Path(dirpath) / name)
    return sorted(files)


def _rel(path):
    return str(Path(path).resolve().relative_to(APP_DIR)).replace("\\", "/")


def _read_lines(path):
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _code_part(line):
    """去掉行尾注释，只留代码部分。

    AI-CI-GREEN-005-F04：T6 的判定对象是**展示给用户看的字符串**，不是开发注释。
    设计说明里同时提到「安全库存」和两个列名是完全合法的（甚至应该写清楚），
    把这类注释算作违规只会逼人把注释写得更含糊，反而丢信息。
    """
    return line.split("#", 1)[0]


def test_t6_no_safety_stock_label_on_min_stock_code():
    """T6：展示文案里的「安全库存」不得与 min_stock 共现（白名单 4 个文件除外）。

    命中条件：某行的**代码部分**含「安全库存」，且其 ±2 行的代码部分窗口内出现
    min_stock。这类共现几乎必然是「文案指 reorder_point、代码却读 min_stock」的错位。
    """
    files = _py_source_files()
    assert len(files) > 50, f"扫描集异常，只找到 {len(files)} 个 .py 文件"

    offenders = []
    for f in files:
        if _rel(f) in T6_ALLOWLIST:
            continue
        lines = [_code_part(l) for l in _read_lines(f)]
        for i, line in enumerate(lines):
            if "安全库存" not in line:
                continue
            window = "\n".join(lines[max(0, i - 2): i + 3])
            if "min_stock" in window:
                offenders.append(f"{_rel(f)}:{i + 1} | {line.strip()[:90]}")

    assert not offenders, (
        "以下位置「安全库存」与 min_stock 共现，极可能是文案与字段错位"
        "（若确实是合法用法，请先确认再把它加进 T6_ALLOWLIST）：\n  "
        + "\n  ".join(offenders)
    )


def test_t7_low_below_safety_stock_only_for_danger_band():
    """T7：.py 中出现「低于安全库存」的行，必须同时含 danger 或 safety_stock。

    「低于安全库存」是 danger 档的专属叫法，判定对象是计算值
    safety_stock = max(reorder_point, min_stock)（`_material_alert_status_values`）。
    凡是判定走 min_stock 的地方，都必须写「低于最低库存」。
    """
    offenders = []
    for f in _py_source_files():
        for i, line in enumerate(_read_lines(f)):
            if "低于安全库存" not in line:
                continue
            if "danger" in line or "safety_stock" in line:
                continue
            offenders.append(f"{_rel(f)}:{i + 1} | {line.strip()[:90]}")

    assert not offenders, (
        "以下位置的「低于安全库存」不在 danger 档标签行上"
        "（判定若走 min_stock，应写「低于最低库存」）：\n  "
        + "\n  ".join(offenders)
    )


# ---------- T8：Android 界面文案（第二个盲区） ----------

# AI-CI-GREEN-005-F04：只扫「会渲染给用户看」的两层：ui/screens（页面）与
# ui/viewmodel（空态/提示文案）。data/** 是 DTO 与接口注释，属于开发者文档，
# 里面解释公式时难免提到历史列名，不纳入扫描。
ANDROID_UI_DIRS = [
    APP_DIR / "android-native-wms/app/src/main/java/com/factory/wms/ui/screens",
    APP_DIR / "android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel",
]


def _android_ui_files():
    files = []
    for d in ANDROID_UI_DIRS:
        if not d.is_dir():
            continue
        files.extend(sorted(d.rglob("*.kt")))
    return files


def test_t8_no_legacy_label_in_android_ui():
    """T8：Android 界面文案不得出现「最小库存 / 再订货点 / 再订购点」。

    正确叫法：min_stock→最低库存，reorder_point→安全库存。手机端查库存结果卡的
    「再订货点」InfoChip 就是这么被发现的——它读的是 reorderPoint，却挂了旧名字。
    """
    files = _android_ui_files()
    assert len(files) > 5, f"扫描集异常，只找到 {len(files)} 个 Kotlin 界面文件"

    offenders = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for legacy in ("最小库存", "再订货点", "再订购点"):
            if legacy in text:
                offenders.append(
                    f"{f.relative_to(APP_DIR / 'android-native-wms')} -> {legacy}"
                )

    assert not offenders, (
        "以下 Android 界面文件仍在用旧叫法（应为「最低库存」/「安全库存」）：\n  "
        + "\n  ".join(offenders)
    )


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASSED")
