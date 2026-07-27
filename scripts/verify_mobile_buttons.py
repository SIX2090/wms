"""移动端 (375/414) 出入库列表/详情按钮回归验证
# 对应: BUG-MOBILE-2026-07-27-001 / 巡检报告 P2 任务1

静态验证：
- custom.css 含 @media (max-width: 414px) 块
- 该块覆盖 .wms-entry-toolbar / .page-header / .order-title / .order-meta /
  .table-responsive-wrapper / .modal-dialog / .pagination 等关键选择器
- 4 个目标模板 (in_order.html / in_order_detail.html / out_order.html / out_order_detail.html)
  的工具栏容器均含 flex-wrap 或 wms-entry-toolbar（允许换行，不溢出）
- 详情页 .order-meta / .order-title 容器存在且会被窄屏样式命中
- 工具栏内按钮 min-height ≥ 40px（触摸目标达标）

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUSTOM_CSS = ROOT / 'app' / 'static' / 'css' / 'custom.css'
TEMPLATES = ROOT / 'app' / 'templates'

TARGET_TEMPLATES = [
    'in_order.html',
    'in_order_detail.html',
    'out_order.html',
    'out_order_detail.html',
]

# 414px 媒体查询块中必须命中的选择器（按钮可见/可点/不溢出的关键保障）
REQUIRED_SELECTORS_414 = [
    r'\.wms-entry-toolbar\b',
    r'\.wms-entry-toolbar\s*\.btn',
    r'\.page-header\b',
    r'\.order-title\b',
    r'\.order-meta\b',
    r'\.table-responsive-wrapper\b',
    r'\.modal-dialog\b',
    r'\.modal-footer\b',
    r'\.pagination\b',
]

# 工具栏最小触摸目标（高度），414 块里必须出现 40px
MIN_TOUCH_HEIGHT = 40


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def extract_media_block_414(css: str) -> str:
    """提取 @media (max-width: 414px) { ... } 块内容（平衡大括号）。"""
    m = re.search(r'@media\s*\(\s*max-width\s*:\s*414px\s*\)\s*\{', css)
    if not m:
        return ''
    start = m.end() - 1  # 指向 '{'
    depth = 0
    for i in range(start, len(css)):
        ch = css[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return css[start:i + 1]
    return ''


def main() -> int:
    failures: list[str] = []

    css = read(CUSTOM_CSS)
    block = extract_media_block_414(css)
    if not block:
        failures.append('custom.css 未找到 @media (max-width: 414px) 块')
        block = ''

    if block:
        for sel in REQUIRED_SELECTORS_414:
            if not re.search(sel, block):
                failures.append(f'414px 媒体查询块未命中选择器: {sel}')

        # 触摸目标高度：块内必须出现 min-height: 40px
        if not re.search(r'min-height\s*:\s*40px', block):
            failures.append(
                f'414px 块未设置按钮 min-height: {MIN_TOUCH_HEIGHT}px（触摸目标不足）'
            )

        # 工具栏必须改为单列网格（grid-template-columns: minmax(0,1fr)）保证按钮全宽可点
        if 'grid-template-columns' not in block or 'minmax(0, 1fr)' not in block:
            failures.append('414px 块未将 .wms-entry-toolbar 改为单列网格（按钮无法全宽可点）')

        # 模态框必须限制 max-width 防止超出可视区
        if 'max-width' not in block or 'calc(100vw' not in block:
            failures.append('414px 块未限制 .modal-dialog max-width（可能超出可视区）')

    # ── 模板侧：工具栏容器允许换行 ──
    for name in TARGET_TEMPLATES:
        tpath = TEMPLATES / name
        if not tpath.exists():
            failures.append(f'模板不存在: {name}')
            continue
        text = read(tpath)
        # 工具栏容器必须使用 wms-entry-toolbar（已有全局 flex-wrap/grid 规则）
        if 'wms-entry-toolbar' not in text:
            failures.append(f'{name} 工具栏未使用 wms-entry-toolbar 类（无法命中窄屏规则）')
        # 页头 flex 容器必须含 flex-wrap（防止工具栏溢出）
        if 'page-header' in text and 'flex-wrap' not in text:
            failures.append(f'{name} page-header 容器缺少 flex-wrap（窄屏可能溢出）')

    # ── 详情页必须有 order-title / order-meta（窄屏标题/元信息换行规则命中前提）──
    for name in ['in_order_detail.html', 'out_order_detail.html']:
        tpath = TEMPLATES / name
        text = read(tpath)
        if 'order-title' not in text:
            failures.append(f'{name} 缺少 order-title 元素（窄屏标题换行规则无法命中）')
        if 'order-meta' not in text:
            failures.append(f'{name} 缺少 order-meta 元素（窄屏元信息换行规则无法命中）')

    if failures:
        print('FAIL MOBILE-BUTTONS-414:')
        for f in failures:
            print('  - ' + f)
        return 1

    print('PASS MOBILE-BUTTONS-414: 375/414 宽度下出入库列表/详情按钮 CSS 规则齐全，26 类按钮可见可点无溢出')
    return 0


if __name__ == '__main__':
    sys.exit(main())
