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
 *   - Enter 语义（AI-WMS-FILTER-004）：↑↓ 高亮后 Enter = 选中该项；
 *     搜索型筛选框（data-ks-submit="1"）直接 Enter = 按当前关键词提交
 *     表单做模糊搜索（输入「电线」回车 → 列表显示所有包含「电线」的物料）；
 *     仅无 submit 标记的纯选择框保留「Enter 选中第一项」
 *   - 保留原 name 与表单行为，不改变后端参数
 *   - 物料候选富展示（AI-WMS-FILTER-005）：物料（data-ks="material"）下拉项
 *     两行展示——上行「编码 + 名称」、下行灰字「规格 · 品牌」，
 *     四个字段均参与关键词高亮，方便按任意字段确认目标物料
 */
(function (window, document) {
    'use strict';

    var API_BASE = '/api/options/';
    var DEBOUNCE_MS = 180;
    var POOL_TTL = 300000;   // 本地候选池有效期 5 分钟
    var MAX_ITEMS = 50;
    var FIRST_FETCH_LIMIT = 200;

    var pools = {};          // entity -> {t, data, remote}
    var seq = 0;             // 共享生命周期序号，关闭/换词/换输入框即失效
    var searchOwner = null;
    var cancelPendingSearch = null;

    /* ---------- 工具 ---------- */

    function esc(s) {
        return String(s === null || s === undefined ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function debounce(fn, ms) {
        var timer = null;
        var delayed = function () {
            var self = this, args = arguments;
            if (timer) clearTimeout(timer);
            timer = setTimeout(function () { timer = null; fn.apply(self, args); }, ms);
        };
        delayed.cancel = function () {
            if (timer) clearTimeout(timer);
            timer = null;
        };
        return delayed;
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
                cb({ data: [], status: 'error' });
            }
        };
        xhr.onerror = function () { cb({ data: [], status: 'error' }); };
        xhr.ontimeout = function () { cb({ data: [], status: 'error' }); };
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

    function getOptions(entity, kw, cb, offset) {
        offset = offset || 0;
        var p = pools[entity];
        function remoteResult(d) {
            var items = d.data || [];
            cb(items, Math.max(Number(d.total) || 0, offset + items.length),
               d.status === 'error' || (offset > 0 && d.offset !== offset));
        }
        function localResult(data) {
            var matches = filterLocal(data, kw);
            cb(matches.slice(offset, offset + MAX_ITEMS), matches.length, false);
        }
        function remoteSearch() {
            ajax(API_BASE + encodeURIComponent(entity) + '?kw=' + encodeURIComponent(kw) +
                 '&limit=' + MAX_ITEMS + (offset ? '&offset=' + offset : ''), remoteResult);
        }

        // 远程模式（大数据集）：每次带关键词请求，服务端做拼音匹配
        if (p && p.remote) {
            remoteSearch();
            return;
        }

        // 本地池命中：直接过滤；无结果时回源一次（服务端可命中拼音）
        if (p && p.data) {
            var local = filterLocal(p.data, kw);
            if (local.length || !kw) { localResult(p.data); return; }
            remoteSearch();
            return;
        }

        // 首次加载：判断走本地池还是远程
        ajax(API_BASE + encodeURIComponent(entity) + '?kw=&limit=' + FIRST_FETCH_LIMIT,
            function (d) {
                var data = d.data || [];
                if (d.status === 'error') { remoteResult(d); return; }
                var remote = (d.total || 0) > data.length;
                pools[entity] = { t: Date.now(), data: data, remote: remote };
                if (remote) {
                    remoteSearch();
                } else {
                    localResult(data);
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
            menu._ksPointerDown = true;
            if (ev.target.closest && ev.target.closest('.ks-more')) {
                ev.preventDefault();
                return;
            }
            var item = ev.target.closest ? ev.target.closest('.ks-item') : null;
            if (!item) return;
            ev.preventDefault();
            var input = menu._ksInput;
            if (!input) return;
            var idx = parseInt(item.getAttribute('data-idx'), 10);
            commit(input, (menu._ksItems || [])[idx]);
            hideMenu();
        });

        menu.addEventListener('click', function (ev) {
            if (ev.target.closest && ev.target.closest('.ks-more')) loadMore();
        });

        document.addEventListener('mouseup', function () {
            menu._ksPointerDown = false;
            var input = menu._ksInput;
            if (input && menu.style.display === 'block' && document.activeElement !== input) {
                input.focus({ preventScroll: true });
            }
        });
        document.addEventListener('scroll', function (ev) {
            if (menu.contains(ev.target)) {
                if (!menu._ksFailed && menu.scrollTop + menu.clientHeight >= menu.scrollHeight - 40) loadMore();
                return;
            }
            hideMenu();
        }, true);
        window.addEventListener('resize', function () { hideMenu(); });
        return menu;
    }

    function positionMenu(input) {
        var r = input.getBoundingClientRect();
        var margin = 8, gap = 3;
        var below = Math.max(0, window.innerHeight - r.bottom - gap - margin);
        var above = Math.max(0, r.top - gap - margin);
        var upward = below < 290 && above > below;
        var width = Math.min(Math.max(r.width, 220), Math.max(0, window.innerWidth - margin * 2));
        menu.style.position = 'fixed';
        menu.style.boxSizing = 'border-box';
        menu.style.width = width + 'px';
        menu.style.left = Math.max(margin, Math.min(r.left, window.innerWidth - margin - width)) + 'px';
        menu.style.top = (r.bottom + 3) + 'px';
        menu.style.minWidth = '0';
        menu.style.maxHeight = Math.min(290, upward ? above : below) + 'px';
        // 空间不足时向上翻转
        if (upward) {
            menu.style.top = '';
            menu.style.bottom = (window.innerHeight - r.top + 3) + 'px';
        } else {
            menu.style.bottom = '';
        }
    }

    // AI-WMS-FILTER-005：物料候选两行富展示——上行「编码 + 名称」、下行「规格 · 品牌」。
    // 库存台账等页面输入「螺丝」时，含螺丝的物料的编码/名称/规格/品牌全部可见，
    // 且四个字段均按关键词高亮（此前只显示编码 + 一段截断的规格文本，看不到名称）。
    function renderMaterialItem(it, idx, kw) {
        var code = it.code || '';
        var name = it.name || '';
        var spec = it.spec || '';
        var brand = it.brand || '';
        var main = code || name || it.label || '';
        var extras = [];
        if (spec) extras.push('规格 ' + highlight(spec, kw));
        if (brand) extras.push('品牌 ' + highlight(brand, kw));
        return '<div class="ks-item ks-item-rich" data-idx="' + idx + '">' +
               '<div class="ks-rich-line1">' +
               '<span class="ks-main">' + highlight(main, kw) + '</span>' +
               (name && name !== main
                   ? '<span class="ks-rich-name">' + highlight(name, kw) + '</span>' : '') +
               '</div>' +
               (extras.length
                   ? '<div class="ks-rich-sub">' + extras.join(' · ') + '</div>' : '') +
               '</div>';
    }

    function renderMenu(input, items, kw, total, failed) {
        menu._ksItems = items;
        menu._ksInput = input;
        menu._ksActive = -1;
        menu._ksKeyword = kw;
        menu._ksValue = input.value;
        menu._ksTotal = total;
        menu._ksLoading = false;
        menu._ksFailed = failed;

        if (!items.length) {
            menu.innerHTML = '<div class="ks-empty">' +
                (failed ? '查询失败，请重新输入重试' : (kw ? '无匹配结果' : '暂无可选数据')) + '</div>';
        } else {
            var entity = input.getAttribute('data-ks') || '';
            var html = '';
            for (var i = 0; i < items.length; i++) {
                var it = items[i];
                if (entity === 'material') {
                    html += renderMaterialItem(it, i, kw);
                    continue;
                }
                var main = it.code || it.name || it.label || '';
                var sub = it.sub || (it.code ? it.name : '');
                html += '<div class="ks-item" data-idx="' + i + '">' +
                        '<span class="ks-main">' + highlight(main, kw) + '</span>' +
                        (sub && sub !== main ? '<span class="ks-sub">' + esc(sub) + '</span>' : '') +
                        '</div>';
            }
            menu.innerHTML = html;
        }
        renderMore();
        menu.scrollTop = 0;
        menu.style.display = 'block';
        positionMenu(input);
    }

    function renderMore() {
        var old = menu.querySelector('.ks-footer');
        if (old) old.remove();
        if (!menu._ksItems.length) return;
        var footer = document.createElement('div');
        footer.className = 'ks-footer';
        var count = menu._ksItems.length;
        footer.innerHTML = '<span>已显示 ' + count + ' / ' + menu._ksTotal + ' 条</span>' +
            (count < menu._ksTotal ? '<button type="button" class="ks-more"' +
             (menu._ksLoading ? ' disabled' : '') + '>' +
             (menu._ksLoading ? '加载中…' : (menu._ksFailed ? '加载失败，点击重试' : '加载更多')) + '</button>' : '');
        menu.appendChild(footer);
    }

    function loadMore() {
        var input = menu && menu._ksInput;
        if (!input || menu.style.display !== 'block' || menu._ksLoading ||
            menu._ksItems.length >= menu._ksTotal) return;
        var ticket = seq, kw = menu._ksKeyword, offset = menu._ksItems.length;
        menu._ksLoading = true;
        renderMore();
        getOptions(input.getAttribute('data-ks'), kw, function (items, total, failed) {
            if (ticket !== seq || !menuVisibleFor(input) || !input.isConnected || input.value !== menu._ksValue) return;
            menu._ksLoading = false;
            menu._ksFailed = failed || !items.length;
            if (!menu._ksFailed) {
                var old = menu.querySelector('.ks-footer');
                if (old) old.remove();
                for (var i = 0; i < items.length; i++) {
                    var idx = menu._ksItems.length;
                    var it = items[i];
                    var html = input.getAttribute('data-ks') === 'material' ? renderMaterialItem(it, idx, kw) :
                        '<div class="ks-item" data-idx="' + idx + '"><span class="ks-main">' +
                        highlight(it.code || it.name || it.label || '', kw) + '</span><span class="ks-sub">' +
                        esc(it.sub || (it.code ? it.name : '') || '') + '</span></div>';
                    menu.insertAdjacentHTML('beforeend', html);
                    menu._ksItems.push(it);
                }
                menu._ksTotal = Math.max(total, menu._ksItems.length);
            }
            renderMore();
        }, offset);
    }

    function hideMenu() {
        seq++;
        if (cancelPendingSearch) cancelPendingSearch();
        cancelPendingSearch = null;
        searchOwner = null;
        if (menu) { menu.style.display = 'none'; menu._ksInput = null; menu._ksPointerDown = false; }
    }

    function menuVisibleFor(input) {
        return menu && menu.style.display === 'block' && menu._ksInput === input;
    }

    function moveActive(step) {
        if (!menu || menu.style.display !== 'block') return;
        var nodes = menu.querySelectorAll('.ks-item');
        if (!nodes.length) return;
        if (step > 0 && menu._ksActive === nodes.length - 1 && menu._ksItems.length < menu._ksTotal) {
            loadMore();
            return;
        }
        var idx = menu._ksActive + step;
        if (idx < 0) idx = nodes.length - 1;
        if (idx >= nodes.length) idx = 0;
        if (menu._ksActive >= 0 && nodes[menu._ksActive]) nodes[menu._ksActive].classList.remove('active');
        menu._ksActive = idx;
        nodes[idx].classList.add('active');
        nodes[idx].scrollIntoView({ block: 'nearest' });
    }

    function activeItem() {
        // AI-WMS-FILTER-004：只认用户 ↑↓ 主动高亮的项，不再默认回退第一项。
        // 「Enter 按输入关键词搜索」与「Enter 选中候选」由调用方据此区分。
        if (!menu) return null;
        var items = menu._ksItems || [];
        var idx = menu._ksActive;
        if (idx >= 0 && items[idx]) return items[idx];
        return null;
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
        var composing = false;   // 中文输入法组合态：期间不触发搜索、不劫持按键

        var doSearch = function (showAll) {
            if (composing || document.activeElement !== input || input.isConnected === false) return;
            hideMenu();
            searchOwner = input;
            cancelPendingSearch = debounced.cancel;
            if (poolExpired(entity)) delete pools[entity];
            var inputValue = input.value || '';
            var kw = showAll ? '' : (input.value || '').trim();
            var ticket = ++seq;
            getOptions(entity, kw, function (items, total, failed) {
                if (ticket !== seq || searchOwner !== input || composing) return;
                if (document.activeElement !== input || input.isConnected === false) return;
                if ((input.value || '') !== inputValue) return;
                ensureMenu();
                renderMenu(input, items, kw, total, failed);
            });
        };

        var debounced = debounce(function () { doSearch(false); }, DEBOUNCE_MS);

        var invalidate = function () {
            debounced.cancel();
            if (searchOwner === input) hideMenu();
        };

        var scheduleSearch = function () {
            hideMenu();
            searchOwner = input;
            cancelPendingSearch = debounced.cancel;
            debounced();
        };

        input.addEventListener('focus', function () { if (!menuVisibleFor(input)) doSearch(false); });
        input.addEventListener('click', function () { if (!menuVisibleFor(input)) doSearch(false); });
        input.addEventListener('compositionstart', function () {
            composing = true;
            invalidate();
        });
        input.addEventListener('compositionend', function () {
            composing = false;
            scheduleSearch();   // 拼音上屏后再按最终文本检索一次
        });
        input.addEventListener('input', function () {
            invalidate();
            if (composing) return;   // 组合态下按临时拼音串检索只会抖动候选
            scheduleSearch();
        });
        input.addEventListener('change', invalidate);

        input.addEventListener('keydown', function (ev) {
            // IME 组合态（拼音上屏）的 Enter/方向键归输入法支配，组件不得拦截，
            // 否则用户按 Enter 上屏会被误判为「选中第一项候选」。
            if (ev.isComposing || ev.keyCode === 229) return;
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
                    // 1) 用户已用 ↑↓ 主动高亮某项：Enter = 确认选中该项
                    var picked = activeItem();
                    if (picked) { ev.preventDefault(); commit(input, picked); hideMenu(); return; }
                    // 2) 搜索型筛选框（data-ks-submit="1"）且无主动高亮：
                    //    放行表单默认提交，让后端按当前关键词做模糊搜索。
                    //    AI-WMS-FILTER-004：物料列表输入「电线」直接回车，
                    //    右侧应显示所有包含「电线」的物料；此前会被劫持成
                    //    选中第一项候选、回填其编码，提交后只剩一条结果。
                    if (input.getAttribute('data-ks-submit') !== '1') {
                        // 3) 纯候选选择框（无 submit 标记）：保留
                        //    「Enter 选中第一项」的效率行为
                        var items = menu._ksItems || [];
                        if (items.length) {
                            ev.preventDefault();
                            commit(input, items[0]);
                            hideMenu();
                            return;
                        }
                    }
                }
                hideMenu();  // 放行，交给表单默认提交
            }
        });

        // 候选 mousedown 已 preventDefault，可先提交；失焦立即撤销旧请求与防抖。
        input.addEventListener('blur', function () {
            if (menuVisibleFor(input) && menu._ksPointerDown) return;
            invalidate();
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
            '.ks-menu{overscroll-behavior:contain}',
            '.ks-footer{display:flex;align-items:center;justify-content:space-between;gap:8px;',
            'padding:8px 10px;color:#64748b;font-size:12px}',
            '.ks-more{border:1px solid #cbd5e1;border-radius:4px;background:#fff;color:#1d4ed8;cursor:pointer;padding:4px 8px}',
            '.ks-item{display:flex;justify-content:space-between;gap:10px;align-items:baseline;',
            'padding:7px 10px;border-radius:6px;cursor:pointer;white-space:nowrap}',
            '.ks-item:hover,.ks-item.active{background:#eff6ff}',
            '.ks-main{overflow:hidden;text-overflow:ellipsis}',
            '.ks-sub{color:#94a3b8;font-size:12px;overflow:hidden;text-overflow:ellipsis;',
            'max-width:60%;white-space:nowrap}',
            '.ks-hl{background:#fde68a;color:#92400e;padding:0 1px;border-radius:2px}',
            '.ks-item-rich{flex-direction:column;align-items:stretch;justify-content:flex-start;',
            'gap:1px;white-space:normal}',
            '.ks-rich-line1{display:flex;gap:8px;align-items:baseline;min-width:0;',
            'white-space:nowrap;overflow:hidden}',
            '.ks-rich-name{color:#475569;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
            '.ks-rich-sub{color:#94a3b8;font-size:12px;overflow:hidden;text-overflow:ellipsis;',
            'white-space:nowrap}',
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
