#!/usr/bin/env python3
"""
扫描 base.html 所有菜单，逐个 HTTP 抓取实际页面 <title>，
对比菜单文字与实际 title，挑出菜单与页面不符的项。
"""
import re
import subprocess
import sys
from html import unescape

BASE = "http://127.0.0.1:8080"
COOKIE = "/tmp/audit/cookie.txt"
BASE_HTML = "/workspace/app/templates/base.html"
OUT_FILE = "/workspace/docs/audit/MENU_PAGE_MISMATCH_REPORT.md"


def fetch(url, timeout=10):
    try:
        out = subprocess.check_output(
            ["curl", "-s", "-b", COOKIE, "-w", "\n__CODE__%{http_code}__SIZE__%{size_download}",
             f"{BASE}{url}"],
            stderr=subprocess.DEVNULL, timeout=timeout,
        ).decode("utf-8", errors="replace")
        if "__CODE__" in out:
            body, tail = out.rsplit("__CODE__", 1)
            code = tail.split("__SIZE__")[0]
            size = tail.split("__SIZE__")[1]
        else:
            body, code, size = out, "000", "0"
        return int(code), body, int(size)
    except subprocess.TimeoutExpired:
        return -1, "", 0
    except Exception as e:
        return -2, str(e), 0


def extract_menu():
    with open(BASE_HTML, "r", encoding="utf-8") as f:
        text = f.read()
    items = []
    pat = re.compile(
        r'<a\s+class="flyout-link"\s+href="([^"]+)"[^>]*>'
        r'\s*(?:<i[^>]*></i>\s*)?([^<]+?)\s*</a>'
    )
    for m in pat.finditer(text):
        url = m.group(1).strip()
        title = unescape(m.group(2).strip())
        if not url or url.startswith("#") or url.startswith("{{"):
            continue
        items.append(("flyout", title, url))
    pat2 = re.compile(
        r'<a\s+class="nav-link"\s+href="([^"]+)"[^>]*>'
        r'(?:<i[^>]*></i>\s*)?([^<]+?)\s*</a>'
    )
    for m in pat2.finditer(text):
        url = m.group(1).strip()
        title = unescape(m.group(2).strip())
        if not url or url.startswith("#") or url.startswith("{{"):
            continue
        items.append(("nav", title, url))
    return items


def extract_title(body):
    m = re.search(r'<title>([^<]+)</title>', body)
    return m.group(1).strip() if m else ""


def extract_h1h2(body):
    out = []
    for m in re.finditer(r'<h([12])[^>]*>([^<]+)', body):
        out.append((int(m.group(1)), m.group(2).strip()))
    return out[:6]


def main():
    items = extract_menu()
    seen = set()
    uniq = []
    for kind, title, url in items:
        key = (url, title)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((kind, title, url))

    print(f"共 {len(uniq)} 条菜单链接")
    print()
    print(f"{'#':>3} {'菜单':<24} {'URL':<40} {'HTTP':<6} {'title':<32} {'h1/h2'}")
    print("-" * 140)

    rows = []
    mismatches = []
    for i, (kind, title, url) in enumerate(uniq, 1):
        code, body, size = fetch(url)
        real_title = extract_title(body) if code == 200 else ""
        h12 = extract_h1h2(body)
        h12_s = " | ".join(f"h{t[0]}:{t[1]}" for t in h12)[:40]
        print(f"{i:>3} {title[:24]:<24} {url[:40]:<40} {code:<6} {real_title[:32]:<32} {h12_s}")
        rows.append((i, kind, title, url, code, real_title, h12))
        if code != 200:
            mismatches.append((i, kind, title, url, code, real_title, h12, "请求失败"))
            continue
        if not real_title:
            mismatches.append((i, kind, title, url, code, real_title, h12, "无 title"))
            continue
        # 关键字比对：业务词命中即视为一致。
        for kw in ('采购入库', '产品入库', '其他入库', '其他出库', '采购申请', '采购订单', '采购单', '销售出库', '销售订单', '售后出库', '领料', '入库明细', '领料明细', '其他入库明细', '其他出库明细', '物料', '合同', '期初库存', '物料分类', '计量单位', '供应商', '客户', '仓库', '部门', '员工', '系统设置', '用户', '审批', '审计', '微信分享', '数据备份', 'BOM', '委外', '库存', '盘点', '调拨', '调整', '补货', 'OCR', '需求预测', '健康度'):
            if kw in title:
                if kw in real_title:
                    break  # 命中，匹配
                rt_strip = re.sub(r'^(新增|编辑|查看|详情)', '', real_title)
                rt_strip = re.sub(r'(单据|管理|报表|列表|明细|中心|档案|页面|台账|记录|建账|工作台|看板|预检|评估|运维|运营|验收|单|标准|模板|请求|详情|服务|配置)$', '', rt_strip)
                if kw in rt_strip:
                    break  # 宽松命中
                mismatches.append((i, kind, title, url, code, real_title, h12, f"菜单含业务词 '{kw}' 但实际 title 不含"))
                break  # 错配
        else:
            # for 循环正常结束（没 break）：菜单里没业务词，做宽松匹配
            norm_title = re.sub(r'(新增|编辑|详情|标准|单据|管理|报表|列表|明细|中心|档案|页面|台账|记录|建账|工作台|看板|预检|评估|运维|运营|验收|单)$', '', title).strip()
            norm_title = re.sub(r'[/／].*$', '', norm_title).strip()
            if norm_title and norm_title not in real_title and real_title not in title:
                rt_no_qx = re.sub(r'^(新增|编辑|查看|详情)', '', real_title).strip()
                rt_no_qx = re.sub(r'(单据|管理|报表|列表|明细|中心|档案|页面|台账|记录|建账|工作台|看板|预检|评估|运维|运营|验收|单|标准|模板|请求|详情|服务|配置)$', '', rt_no_qx).strip()
                if norm_title and (norm_title in rt_no_qx or norm_title in real_title):
                    pass
                else:
                    if real_title in ("首页", "Redirecting...", "登录", "仓库管理系统", ""):
                        pass
                    else:
                        mismatches.append((i, kind, title, url, code, real_title, h12, f"title 不含 '{norm_title}'"))

    print()
    print("=" * 80)
    print(f"不匹配项: {len(mismatches)}")
    print("=" * 80)

    # 写报告
    import os
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("# WMS 菜单 vs 实际页面 错配报告\n\n")
        f.write("扫描范围：`app/templates/base.html` 中所有 `class=\"flyout-link\"` 和 `class=\"nav-link\"` 菜单项\n\n")
        f.write(f"共扫描 **{len(uniq)}** 条菜单链接，发现 **{len(mismatches)}** 条菜单文字与实际页面不一致。\n\n")
        f.write("## 1. 全部菜单访问结果\n\n")
        f.write("| # | 菜单 | URL | HTTP | 实际 title | h1/h2 |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        for r in rows:
            i, kind, title, url, code, rt, h12 = r
            h12_s = "<br>".join(f"h{t[0]}:{t[1]}" for t in h12[:2]) or "-"
            f.write(f"| {i} | {title} | `{url}` | {code} | {rt or '-'} | {h12_s} |\n")
        f.write("\n## 2. 菜单与实际页面不符清单（按严重程度排序）\n\n")
        f.write("| # | 菜单 | URL | HTTP | 实际 title | h1/h2 | 原因 |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- |\n")
        # 按 kind 区分：flyout 优先（侧边栏），nav 优先级低
        mismatches.sort(key=lambda x: (0 if x[1] == "flyout" else 1, x[0]))
        for m in mismatches:
            i, kind, title, url, code, rt, h12, reason = m
            h12_s = "<br>".join(f"h{t[0]}:{t[1]}" for t in h12[:2]) or "-"
            f.write(f"| {i} | **{title}** | `{url}` | {code} | {rt or '-'} | {h12_s} | {reason} |\n")
        f.write(f"\n报告生成时间：{subprocess.check_output(['date']).decode().strip()}\n")
    print(f"\n报告已写入 {OUT_FILE}")


if __name__ == "__main__":
    main()
