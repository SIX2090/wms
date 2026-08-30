/*!
 * quick-select —— 通用关键词匹配选择组件（AI-WMS-FILTER-001）
 *
 * 用法（无需写任何 JS）：
 *   <input class="form-control" name="contract_no"
 *          data-ks="contract"                  实体类型（对应 /api/options/<entity>）
 *          data-ks-put="code"                  选中后填入输入框的字段，默认 label
 *          data-ks-id="#contractId"            可选：把 id 写入该隐藏框
 *          data-ks-submit="1"                  可选：选中后自动提交所在表单
 *          placeholder="输入关键词选择合同">
 *
 * 特性：
 *   - 输入即出候选，中文子串 + 服务端拼音/首字母匹配
 *   - 小数据集一次拉取本地过滤（零延迟），大数据集自动切换远程搜索
 *   - 键盘操作：↑ ↓ 选择，Enter 确认，Esc 关闭
 *   - 保留原 name 与表单行为，不改变后端参数
 */
(function (window, document) {
    'use strict';

    var API_BASE = '/api/options/';
    var DEBOUNCE_MS = 180;
    var POOL_TTL = 300000;   // 本地候选池有效期 5 分钟
    var MAX_ITEMS = 50;
    var FIRST_FETCH_LIMIT = 200;

    var pools = {};          // entity -> {t, data, remote}
    var seq = 0;             // 请求序号，避免旧响应覆盖新结果

    /* ---------- 工具 ---------- */

    function esc(s) {
        return String(s === null || s === undefined ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function debounce(fn, ms) {
        var timer = null;
        return function () {
            var self = this, args = arguments;
            if (timer) clearTimeout(timer);
            timer = setTimeout(function () { fn.apply(self, args); }, ms);
        };
    }

    function ajax(url, cb) {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.timeout = 8000;
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            if (xhr.status === 200) {
                var data = null;
                try { data = JSON.parse(xhr.responseText); } catch (e) { data = null; }
                cb(data || { data: [] });
            } else {
                cb({ data: [] });
            }
        };
        xhr.onerror = function () { cb({ data: [] }); };
        xhr.ontimeout = function () { cb({ data: [] }); };
        xhr.send(null);
    }

    function highlight(text, kw) {
        var s = esc(text);
        if (!kw) return s;
        var k = esc(kw);
        var idx = s.toLowerCase().indexOf(k.toLowerCase());
        if (idx === -1) return s;
        return s.slice(0, idx) + '<mark class="ks-hl">' + s.slice(idx, idx + k.length) +
               '</mark>' + s.slice(idx + k.length);
    }

    /* ---------- 候选数据 ---------- */

    function filterLocal(data, kw) {
        if (!kw) return data;
        var low = kw.toLowerCase();
        var out = [];
        for (var i = 0; i < data.length; i++) {
            var it = data[i];
            var hay = ((it.code || '') + ' ' + (it.name || '') + ' ' + (it.sub || '')).toLowerCase();
            if (hay.indexOf(low) !== -1) out.push(it);
        }
        return out;
    }

    function getOptions(entity, kw, cb) {
        var p = pools[entity];

        // 远程模式（大数据集）：每次带关键词请求，服务端做拼音匹配
        if (p && p.remote) {
            ajax(API_BASE + encodeURIComponent(entity) + '?kw=' + encodeURIComponent(kw) +
                 '&limit=' + MAX_ITEMS, function (d) { cb(d.data || [], true); });
            return;
        }

        // 本地池命中：直接过滤；无结果时回源一次（服务端可命中拼音）
        if (p && p.data) {
            var local = filterLocal(p.data, kw);
            if (local.length || !kw) { cb(local.slice(0, MAX_ITEMS), false); return; }
            ajax(API_BASE + encodeURIComponent(entity) + '?kw=' + encodeURIComponent(kw) +
                 '&limit=' + MAX_ITEMS, function (d) { cb(d.data || [], true); });
            return;
        }

        // 首次加载：判断走本地池还是远程
        ajax(API_BASE + encodeURIComponent(entity) + '?kw=&limit=' + FIRST_FETCH_LIMIT,
            function (d) {
                var data = d.data || [];
                var remote = (d.total || 0) > data.length;
                pools[entity] = { t: Date.now(), data: data, remote: remote };
                if (remote && kw) {
                    ajax(API_BASE + encodeURIComponent(entity) + '?kw=' +
                         encodeURIComponent(kw) + '&limit=' + MAX_ITEMS,
                         function (d2) { cb(d2.data || [], true); });
                } else {
                    cb(filterLocal(data, kw).slice(0, MAX_ITEMS), false);
                }
            });
    }

    function poolExpired(entity) {
        var p = pools[entity];
        if (!p) return true;
        if (p.remote) return false;
        return (Date.now() - p.t) > POOL_TTL;
    }

    /* ---------- 下拉菜单 ---------- */

    var menu = null;

    function ensureMenu() {
        if (menu) return menu;
        menu = document.createElement('div');
        menu.className = 'ks-menu';
        menu.style.display = 'none';
        document.body.appendChild(menu);

        menu.addEventListener('mousedown', function (ev) {
            var item = ev.target.closest ? ev.target.closest('.ks-item') : null;
            if (!item) return;
            ev.preventDefault();
            var input = menu._ksInput;
            if (!input) return;
            var idx = parseInt(item.getAttribute('data-idx'), 10);
            commit(input, (menu._ksItems || [])[idx]);
            hideMenu();
        });

        document.addEventListener('scroll', function () { hideMenu(); }, true);
        window.addEventListener('resize', function () { hideMenu(); });
        return menu;
    }

    function positionMenu(input) {
        var r = input.getBoundingClientRect();
        menu.style.position = 'fixed';
        menu.style.left = r.left + 'px';
        menu.style.top = (r.bottom + 3) + 'px';
        menu.style.minWidth = Math.max(r.width, 220) + 'px';
        menu.style.maxWidth = Math.max(r.width, 420) + 'px';
        // 空间不足时向上翻转
        var spaceBelow = window.innerHeight - r.bottom;
        if (spaceBelow < 200 && r.top > 200) {
            menu.style.top = '';
            menu.style.bottom = (window.innerHeight - r.top + 3) + 'px';
        } else {
            menu.style.bottom = '';
        }
    }

    function renderMenu(input, items, kw) {
        menu._ksItems = items;
        menu._ksInput = input;
        menu._ksActive = -1;

        if (!items.length) {
            menu.innerHTML = '<div class="ks-empty">' +
                (kw ? '无匹配结果' : '暂无可选数据') + '</div>';
        } else {
            var html = '';
            for (var i = 0; i < items.length; i++) {
                var it = items[i];
                var main = it.code || it.name || it.label || '';
                var sub = it.sub || (it.code ? it.name : '');
                html += '<div class="ks-item" data-idx="' + i + '">' +
                        '<span class="ks-main">' + highlight(main, kw) + '</span>' +
                        (sub && sub !== main ? '<span class="ks-sub">' + esc(sub) + '</span>' : '') +
                        '</div>';
            }
            menu.innerHTML = html;
        }
        menu.style.display = 'block';
        positionMenu(input);
    }

    function hideMenu() {
        if (menu) { menu.style.display = 'none'; menu._ksInput = null; }
    }

    function menuVisibleFor(input) {
        return menu && menu.style.display === 'block' && menu._ksInput === input;
    }

    function moveActive(step) {
        if (!menu || menu.style.display !== 'block') return;
        var nodes = menu.querySelectorAll('.ks-item');
        if (!nodes.length) return;
        var idx = menu._ksActive + step;
        if (idx < 0) idx = nodes.length - 1;
        if (idx >= nodes.length) idx = 0;
        if (menu._ksActive >= 0 && nodes[menu._ksActive]) nodes[menu._ksActive].classList.remove('active');
        menu._ksActive = idx;
        nodes[idx].classList.add('active');
        nodes[idx].scrollIntoView({ block: 'nearest' });
    }

    function activeItem() {
        if (!menu) return null;
        var items = menu._ksItems || [];
        var idx = menu._ksActive;
        if (idx >= 0 && items[idx]) return items[idx];
        return items[0] || null;
    }

    /* ---------- 选中回填 ---------- */

    function commit(input, item) {
        if (!item) return;
        var put = input.getAttribute('data-ks-put') || 'label';
        var val = item[put];
        if (val === undefined || val === null) val = item.label || '';
        input.value = val;

        var idSel = input.getAttribute('data-ks-id');
        if (idSel) {
            var hidden = document.querySelector(idSel);
            if (hidden) hidden.value = (item.id === undefined || item.id === null) ? '' : item.id;
        }
        try { input.dispatchEvent(new Event('change', { bubbles: true })); } catch (e) {}

        if (input.getAttribute('data-ks-submit') === '1') {
            var form = input.form;
            if (form) {
                try {
                    if (typeof form.requestSubmit === 'function') form.requestSubmit();
                    else form.submit();
                } catch (e) { form.submit(); }
            }
        }
    }

    /* ---------- 绑定 ---------- */

    function bind(input) {
        if (input.dataset.ksReady === '1') return;
        input.dataset.ksReady = '1';
        input.setAttribute('autocomplete', 'off');
        input.classList.add('ks-input');

        var entity = input.getAttribute('data-ks');
        var mySeq = 0;

        var doSearch = function (showAll) {
            if (poolExpired(entity)) delete pools[entity];
            var kw = showAll ? '' : (input.value || '').trim();
            var ticket = ++mySeq;
            getOptions(entity, kw, function (items) {
                if (ticket !== mySeq) return;             // 丢弃过期响应
                if (document.activeElement !== input && !showAll) return;
                ensureMenu();
                renderMenu(input, items, kw);
            });
        };

        var debounced = debounce(function () { doSearch(false); }, DEBOUNCE_MS);

        input.addEventListener('focus', function () { doSearch(false); });
        input.addEventListener('click', function () { if (!menuVisibleFor(input)) doSearch(false); });
        input.addEventListener('input', function () { debounced(); });

        input.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape') { hideMenu(); return; }
            if (ev.key === 'ArrowDown') {
                if (!menuVisibleFor(input)) { doSearch(true); return; }
                ev.preventDefault(); moveActive(1); return;
            }
            if (ev.key === 'ArrowUp') {
                if (!menuVisibleFor(input)) return;
                ev.preventDefault(); moveActive(-1); return;
            }
            if (ev.key === 'Enter') {
                if (menuVisibleFor(input)) {
                    var it = activeItem();
                    if (it) { ev.preventDefault(); commit(input, it); hideMenu(); return; }
                }
                hideMenu();  // 无候选时放行，交给表单默认提交
            }
        });

        input.addEventListener('blur', function () {
            setTimeout(function () {
                if (menu && menu._ksInput === input) hideMenu();
            }, 180);
        });
    }

    function init() {
        ensureMenu();
        var nodes = document.querySelectorAll('input[data-ks]');
        for (var i = 0; i < nodes.length; i++) bind(nodes[i]);
    }

    /* ---------- 样式 ---------- */

    function injectStyle() {
        if (document.getElementById('ks-style')) return;
        var css = [
            '.ks-menu{display:none;background:#fff;border:1px solid #d0d7de;border-radius:8px;',
            'box-shadow:0 8px 24px rgba(15,23,42,.16);max-height:290px;overflow-y:auto;',
            'z-index:99999;padding:4px;font-size:13.5px;line-height:1.5}',
            '.ks-item{display:flex;justify-content:space-between;gap:10px;align-items:baseline;',
            'padding:7px 10px;border-radius:6px;cursor:pointer;white-space:nowrap}',
            '.ks-item:hover,.ks-item.active{background:#eff6ff}',
            '.ks-main{overflow:hidden;text-overflow:ellipsis}',
            '.ks-sub{color:#94a3b8;font-size:12px;overflow:hidden;text-overflow:ellipsis;',
            'max-width:60%;white-space:nowrap}',
            '.ks-hl{background:#fde68a;color:#92400e;padding:0 1px;border-radius:2px}',
            '.ks-empty{padding:10px;color:#94a3b8;text-align:center}',
            '.ks-input{background-image:url("data:image/svg+xml;charset=utf8,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'12\' height=\'12\' viewBox=\'0 0 16 16\'%3E%3Cpath fill=\'%2394a3b8\' d=\'M1.5 4.5L8 11l6.5-6.5z\'/%3E%3C/svg%3E");',
            'background-repeat:no-repeat;background-position:right 8px center;padding-right:24px}'
        ].join('');
        var s = document.createElement('style');
        s.id = 'ks-style';
        s.appendChild(document.createTextNode(css));
        document.head.appendChild(s);
    }

    /* ---------- 启动 ---------- */

    function boot() {
        injectStyle();
        init();
        // 动态插入的表单（弹窗/抽屉）也要能生效
        if (window.MutationObserver) {
            var timer = null;
            new MutationObserver(function () {
                if (timer) clearTimeout(timer);
                timer = setTimeout(init, 120);
            }).observe(document.body, { childList: true, subtree: true });
        }
        document.addEventListener('click', function (ev) {
            if (!menu || menu.style.display !== 'block') return;
            var t = ev.target;
            if (t === menu || menu.contains(t)) return;
            if (t && t.getAttribute && t.getAttribute('data-ks')) return;
            hideMenu();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

    window.QuickSelect = {
        init: init,
        refresh: function () { pools = {}; }
    };
})(window, document);
