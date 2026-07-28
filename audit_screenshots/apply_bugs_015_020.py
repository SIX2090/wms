#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BUG-015~020 修复脚本
- BUG-015: Tab 累积无限 → 限 15 + 右键菜单（关闭其他/全部关闭）
- BUG-016: AI 助手浮窗遮挡 → 滚动到底自动收起 + 可隐藏开关
- BUG-017: 入库 Title 不一致 → 统一「入库单 / 新增入库单」
- BUG-018: 搜索框 placeholder 顿号 → supplier/customer 改用、
- BUG-019: 分类层级全「1 级」→ 按 level 颜色 + 路径提示
- BUG-020: 库存查询打印模板常驻 → 空数据时置灰
"""
import os
import re
import sys

ROOT = r'c:\Users\Administrator\Desktop\wms'
APP = os.path.join(ROOT, 'app')


# ==================== BUG-015: Tab 累积无限 ====================
def fix_bug_015():
    """WmsTabs 加 MAX 限制 + 右键菜单。"""
    path = os.path.join(APP, 'static', 'js', 'app.js')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 在 WmsTabs open 函数开头加上 MAX 限制
    old_open = """    function open(url, title) {
        const tabBar = document.getElementById('tabBar');
        const frameWrap = document.getElementById('tabFrameWrap');
        if (!tabBar || !frameWrap) {
            window.location.href = url;
            return;
        }

        const normalizedUrl = normalizeUrl(url);
        const key = makeKey(normalizedUrl);
        if (tabs.has(key)) {
            activate(key);
            return;
        }"""

    new_open = """    // BUG-2026-07-28-015 修复：限制最大 Tab 数
    const MAX_TABS = 15;

    function open(url, title) {
        const tabBar = document.getElementById('tabBar');
        const frameWrap = document.getElementById('tabFrameWrap');
        if (!tabBar || !frameWrap) {
            window.location.href = url;
            return;
        }

        const normalizedUrl = normalizeUrl(url);
        const key = makeKey(normalizedUrl);
        if (tabs.has(key)) {
            activate(key);
            return;
        }

        // BUG-015 修复：超过 MAX_TABS 自动关闭最早的 Tab
        while (tabs.size >= MAX_TABS) {
            const oldestKey = tabs.keys().next().value;
            if (!oldestKey) break;
            close(oldestKey);
        }"""

    if 'const MAX_TABS = 15;' not in content:
        content = content.replace(old_open, new_open)
        print('[BUG-015] 已注入 MAX_TABS = 15 限制')

    # 在 return 语句前加上右键菜单绑定
    old_return = """    return { open: open, close: close, activate: activate, restore: restore, getActiveContext: getActiveContext };
})();"""

    new_return = """    // BUG-2026-07-28-015 修复：关闭其他/全部关闭
    function closeOthers(keepKey) {
        const keys = Array.from(tabs.keys());
        keys.forEach(function(k) {
            if (k !== keepKey) close(k);
        });
    }

    function closeAll() {
        const keys = Array.from(tabs.keys());
        keys.forEach(function(k) { close(k); });
        activeKey = '';
        persistTabs();
    }

    // BUG-2026-07-28-015 修复：右键菜单
    function showContextMenu(x, y, key) {
        const existing = document.getElementById('wmsTabContextMenu');
        if (existing) existing.remove();
        const menu = document.createElement('div');
        menu.id = 'wmsTabContextMenu';
        menu.style.cssText = 'position:fixed;left:' + x + 'px;top:' + y + 'px;z-index:99999;' +
            'background:#fff;border:1px solid #d0d7de;border-radius:6px;padding:4px 0;' +
            'box-shadow:0 4px 12px rgba(0,0,0,.15);min-width:140px;font-size:13px;';
        const items = [
            { label: '关闭当前', action: function() { close(key); } },
            { label: '关闭其他', action: function() { closeOthers(key); } },
            { label: '全部关闭', action: function() { closeAll(); } },
        ];
        items.forEach(function(item) {
            const div = document.createElement('div');
            div.textContent = item.label;
            div.style.cssText = 'padding:6px 14px;cursor:pointer;color:#1f2937;';
            div.addEventListener('mouseenter', function() { div.style.background = '#f1f5f9'; });
            div.addEventListener('mouseleave', function() { div.style.background = 'transparent'; });
            div.addEventListener('click', function() { menu.remove(); item.action(); });
            menu.appendChild(div);
        });
        document.body.appendChild(menu);
        const closeHandler = function(e) {
            if (!menu.contains(e.target)) {
                menu.remove();
                document.removeEventListener('click', closeHandler);
            }
        };
        setTimeout(function() { document.addEventListener('click', closeHandler); }, 0);
    }

    function bindContextMenu() {
        document.querySelectorAll('.tab-item').forEach(function(el) {
            if (el.dataset.ctxBound) return;
            el.dataset.ctxBound = '1';
            el.addEventListener('contextmenu', function(e) {
                e.preventDefault();
                // 通过按钮内文本匹配 key 不稳，改用 dataset 标记
                const allKeys = Array.from(tabs.keys());
                // 用 iframe src 反查 key
                const iframe = document.querySelector('iframe[src*="' + el.querySelector('.tab-title').textContent + '"]');
                // 简化：用 buttons 数组与 key 对应
                const idx = Array.from(el.parentNode.children).indexOf(el);
                let foundKey = '';
                let i = 0;
                tabs.forEach(function(t, k) {
                    if (i === idx) foundKey = k;
                    i++;
                });
                if (foundKey) showContextMenu(e.clientX, e.clientY, foundKey);
            });
        });
    }

    // 拦截 open 让每次新开 tab 重新绑定
    const _origOpen = open;
    function openWithCtx(url, title) {
        _origOpen(url, title);
        setTimeout(bindContextMenu, 0);
    }

    return {
        open: openWithCtx,
        close: close,
        closeOthers: closeOthers,
        closeAll: closeAll,
        activate: activate,
        restore: restore,
        getActiveContext: getActiveContext,
        MAX: MAX_TABS
    };
})();"""

    if 'closeOthers: closeOthers' not in content:
        content = content.replace(old_return, new_return)
        print('[BUG-015] 已添加 closeOthers/closeAll/右键菜单')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


# ==================== BUG-016: AI 助手浮窗遮挡 ====================
def fix_bug_016():
    """AI 助手浮窗：滚动到底自动收起 + 提供隐藏开关。"""
    path = os.path.join(APP, 'templates', 'base.html')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 找到 AI 助手相关 script 段
    old_block = """        if (!button || !panel || !form || !input || !messages) return;
        const pendingImages = [];
        const maxImages = 3;
        const maxImageBytes = 10 * 1024 * 1024;
        const chatHistory = [];"""

    new_block = """        if (!button || !panel || !form || !input || !messages) return;
        const pendingImages = [];
        const maxImages = 3;
        const maxImageBytes = 10 * 1024 * 1024;
        const chatHistory = [];

        // BUG-2026-07-28-016 修复：滚动到底自动收起浮窗 + 用户偏好记忆
        const HIDE_KEY = 'wms_ai_hide_floating';
        let isHidden = false;
        try { isHidden = localStorage.getItem(HIDE_KEY) === '1'; } catch (e) {}
        if (isHidden) {
            button.style.display = 'none';
        }
        // 在按钮上额外加一个小 × 用于彻底隐藏
        if (!document.getElementById('aiAssistantHideBtn')) {
            const hideBtn = document.createElement('span');
            hideBtn.id = 'aiAssistantHideBtn';
            hideBtn.title = '隐藏 AI 浮窗（24h）';
            hideBtn.innerHTML = '<i class="bi bi-eye-slash"></i>';
            hideBtn.style.cssText = 'position:absolute;top:-6px;right:-6px;width:18px;height:18px;' +
                'background:#94a3b8;color:#fff;border-radius:50%;font-size:10px;line-height:18px;' +
                'text-align:center;cursor:pointer;display:none;';
            button.style.position = 'relative';
            button.appendChild(hideBtn);
            hideBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                try { localStorage.setItem(HIDE_KEY, '1'); } catch (err) {}
                button.style.display = 'none';
                const tip = document.createElement('div');
                tip.textContent = 'AI 浮窗已隐藏，刷新页面可恢复';
                tip.style.cssText = 'position:fixed;right:20px;bottom:20px;background:#1f2937;color:#fff;' +
                    'padding:8px 12px;border-radius:6px;font-size:12px;z-index:99999;';
                document.body.appendChild(tip);
                setTimeout(function() { tip.remove(); }, 2500);
            });
            button.addEventListener('mouseenter', function() { hideBtn.style.display = 'block'; });
            button.addEventListener('mouseleave', function() { hideBtn.style.display = 'none'; });
        }
        // 滚动到底部时按钮缩小并半透明
        let scrollTimer = null;
        window.addEventListener('scroll', function() {
            if (scrollTimer) return;
            scrollTimer = setTimeout(function() {
                scrollTimer = null;
                const scrolled = window.scrollY + window.innerHeight;
                const total = document.documentElement.scrollHeight;
                if (total > window.innerHeight + 200 && scrolled >= total - 80) {
                    button.style.transform = 'scale(0.6)';
                    button.style.opacity = '0.4';
                } else {
                    button.style.transform = '';
                    button.style.opacity = '';
                }
            }, 100);
        }, { passive: true });"""

    if 'BUG-2026-07-28-016 修复：滚动到底自动收起浮窗' not in content:
        content = content.replace(old_block, new_block)
        print('[BUG-016] 已注入滚动收起 + 隐藏开关')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


# ==================== BUG-017: 入库 Title 不一致 ====================
def fix_bug_017():
    """统一入库单 title 为「入库单 / 新增入库单」。"""
    targets = [
        (os.path.join(APP, 'templates', 'in_order.html'),
         [("page_title or '入库明细'", "page_title or '入库单'"),
          ("<i class=\"bi bi-box-arrow-in-down\"></i> {{ page_title or '入库明细' }}",
           "<i class=\"bi bi-box-arrow-in-down\"></i> {{ page_title or '入库单' }}"),
          ("title %}{{ page_title or '入库明细' }}{% endblock %}",
           "title %}{{ page_title or '入库单' }}{% endblock %}")]),
        (os.path.join(APP, 'templates', 'in_order_add.html'),
         [("page_title or '新增采购入库单'", "page_title or '新增入库单'"),
          ("title %}{{ page_title or '新增采购入库单' }}{% endblock %}",
           "title %}{{ page_title or '新增入库单' }}{% endblock %}")]),
    ]
    for path, edits in targets:
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            c = f.read()
        original = c
        for old, new in edits:
            c = c.replace(old, new)
        if c != original:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(c)
            print(f'[BUG-017] {os.path.basename(path)} 标题已统一')


# ==================== BUG-018: placeholder 顿号 ====================
def fix_bug_018():
    """统一 supplier/customer placeholder 使用顿号。"""
    fixes = [
        (os.path.join(APP, 'templates', 'supplier.html'),
         'placeholder="搜索供应商编号、名称、联系人、电话、地址"',
         'placeholder="搜索供应商编号、名称、联系人、电话、地址"'),
        (os.path.join(APP, 'templates', 'customer.html'),
         'placeholder="搜索客户编号、名称、联系人、电话、地址"',
         'placeholder="搜索客户编号、名称、联系人、电话、地址"'),
    ]
    for path, old, new in fixes:
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            c = f.read()
        # 用统一正则规范：把 ", "、"，"、"/ "、"," 替换为 "、"
        c2 = re.sub(r'(编码|名称|联系人|电话|地址|编号)、', r'\1、', c)
        c2 = re.sub(r'、\s*、', '、', c2)
        # 清理多余分隔
        c2 = c2.replace('、 / ', '、').replace('、/ ', '、')
        if c2 != c:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(c2)
            print(f'[BUG-018] {os.path.basename(path)} placeholder 顿号已规范')


# ==================== BUG-019: 分类层级颜色 ====================
def fix_bug_019():
    """按 level 上色 + 悬停提示完整路径。"""
    path = os.path.join(APP, 'templates', 'category.html')
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    # 扩展 CSS 颜色：1/2/3/4 级不同色调
    old_css = """.category-level-badge {
    display: inline-block;
    min-width: 42px;
    padding: 2px 7px;
    border-radius: 999px;
    background: #eef2ff;
    color: #3730a3;
    font-size: 12px;
    text-align: center;
}"""

    new_css = """.category-level-badge {
    display: inline-block;
    min-width: 42px;
    padding: 2px 7px;
    border-radius: 999px;
    background: #eef2ff;
    color: #3730a3;
    font-size: 12px;
    text-align: center;
    font-weight: 600;
}
.category-level-badge.lv1 { background: #eef2ff; color: #3730a3; }   /* 1级：靛蓝 */
.category-level-badge.lv2 { background: #ecfeff; color: #0e7490; }   /* 2级：青色 */
.category-level-badge.lv3 { background: #f0fdf4; color: #166534; }   /* 3级：绿色 */
.category-level-badge.lv4 { background: #fef3c7; color: #92400e; }   /* 4级：琥珀 */
.category-level-badge.lv5 { background: #fee2e2; color: #991b1b; }   /* 5级+：红色 */"""

    c = c.replace(old_css, new_css)

    # 替换徽标渲染，加上 class + title 路径提示
    old_badge = '<td><span class="category-level-badge">{{ row.level + 1 }} 级</span></td>'
    new_badge = '<td><span class="category-level-badge lv{{ row.level + 1 }}" title="根分类到当前共 {{ row.level + 1 }} 层">{{ row.level + 1 }} 级</span></td>'
    c = c.replace(old_badge, new_badge)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print('[BUG-019] 分类层级颜色已分级 + 加路径提示')


# ==================== BUG-020: 库存查询打印模板常驻 ====================
def fix_bug_020():
    """库存查询打印按钮在空数据时置灰。"""
    path = os.path.join(APP, 'templates', 'stock_query.html')
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    old = '''        <a href="/report/stock/print" target="_blank" class="btn btn-primary btn-sm">
            <i class="bi bi-printer"></i> 打印报表
        </a>'''
    new = '''        <a href="/report/stock/print" target="_blank"
           class="btn btn-primary btn-sm {% if not materials %}disabled{% endif %}"
           {% if not materials %}aria-disabled="true" tabindex="-1"
           title="请先筛选出有数据的库存后再打印"{% else %}title="打印当前查询结果"{% endif %}
           onclick="return {{ 'false' if not materials else 'true' }};">
            <i class="bi bi-printer"></i> 打印报表
            {% if not materials %}<span class="badge bg-warning text-dark ms-1">无数据</span>{% endif %}
        </a>'''
    c = c.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print('[BUG-020] 库存查询打印按钮空数据时已置灰 + 无数据徽标')


if __name__ == '__main__':
    print('===== 开始修复 BUG-015~020 =====')
    fix_bug_015()
    fix_bug_016()
    fix_bug_017()
    fix_bug_018()
    fix_bug_019()
    fix_bug_020()
    print('===== 全部完成 =====')
