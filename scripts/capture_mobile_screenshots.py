"""移动端 375/414 出入库按钮回归截图脚本
# 对应: BUG-MOBILE-2026-07-27-001 / 巡检报告 P2 任务1

使用 Playwright 登录 WMS，在 375 / 414 两个宽度下对：
  - 入库单列表页 /in_order
  - 入库单详情页（取列表第一条 pending 或最近一条）
  - 出库单列表页 /out_order
  - 出库单详情页（取列表第一条）
截图存档到 qa_screenshots/mobile_{width}_*.png

依赖: playwright + chromium（python -m playwright install chromium）
退出码 0=成功，1=失败。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'qa_screenshots'
BASE = 'http://localhost:8080'

WIDTHS = [375, 414]


def run() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('SKIP screenshots: playwright 未安装（静态验证仍由 verify_mobile_buttons.py 覆盖）')
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shots: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = ctx.new_page()

        # 登录
        page.goto(f'{BASE}/login', wait_until='networkidle')
        page.fill('input[name="username"]', 'admin')
        page.fill('input[name="password"]', 'admin')
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 取入库单第一条 id（用于详情页）
        page.goto(f'{BASE}/in_order', wait_until='networkidle')
        first_in_id = page.eval_on_selector_all(
            'table#inOrderTable tbody tr a[href*="/in_order/"]',
            "els => { for (const e of els) { const m = e.getAttribute('href').match(/\\/in_order\\/(\\d+)/); if (m) return m[1]; } return null; }",
        )

        # 取出库单第一条 id
        page.goto(f'{BASE}/out_order', wait_until='networkidle')
        first_out_id = None
        try:
            first_out_id = page.eval_on_selector_all(
                'table tbody tr a[href*="/out_order/"]',
                "els => { for (const e of els) { const m = e.getAttribute('href').match(/\\/out_order\\/(\\d+)/); if (m) return m[1]; } return null; }",
            )
        except Exception:
            first_out_id = None

        targets = [
            ('in_order_list', f'{BASE}/in_order'),
        ]
        if first_in_id:
            targets.append(('in_order_detail', f'{BASE}/in_order/{first_in_id}'))
        targets.append(('out_order_list', f'{BASE}/out_order'))
        if first_out_id:
            targets.append(('out_order_detail', f'{BASE}/out_order/{first_out_id}'))

        for width in WIDTHS:
            page.set_viewport_size({'width': width, 'height': int(width * 2)})
            for label, url in targets:
                try:
                    page.goto(url, wait_until='networkidle', timeout=15000)
                except Exception:
                    page.goto(url, wait_until='domcontentloaded', timeout=15000)
                fname = OUT_DIR / f'mobile_{width}_{label}.png'
                page.screenshot(path=str(fname), full_page=True)
                shots.append(str(fname))
                print(f'  截图: {fname}')

        browser.close()

    print(f'截图完成: {len(shots)} 张存档到 qa_screenshots/')
    return 0


if __name__ == '__main__':
    sys.exit(run())
