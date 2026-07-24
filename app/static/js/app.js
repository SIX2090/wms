// 全局确认框队列
let confirmResolver = null;
let confirmQueue = [];
let activeConfirm = null;

// Toast 图标映射
function getToastIcon(type) {
    const icons = {
        success: 'bi-check-circle-fill',
        danger: 'bi-x-circle-fill',
        warning: 'bi-exclamation-triangle-fill',
        info: 'bi-info-circle-fill',
        secondary: 'bi-bell-fill'
    };
    return icons[type] || icons.info;
}

// Toast 通知
function toast(message, type, duration) {
    type = type || 'info';
    duration = duration || 2600;
    const stack = document.getElementById('cbToastStack');
    if (!stack) {
        alert(message);
        return;
    }

    const item = document.createElement('div');
    item.className = 'cb-toast cb-toast-' + type;
    // XSS 防护：使用 DOM API 构建，message 通过 textContent 设置，避免 innerHTML 注入
    item.innerHTML =
        '<div class="cb-toast-icon"><i class="bi ' + getToastIcon(type) + '"></i></div>' +
        '<div class="cb-toast-body"></div>' +
        '<button type="button" class="cb-toast-close" aria-label="关闭"><i class="bi bi-x-lg"></i></button>';
    // 消息内容通过 textContent 写入，确保任何字符串都被当作纯文本渲染
    var bodyNode = item.querySelector('.cb-toast-body');
    if (bodyNode) {
        bodyNode.textContent = message == null ? '' : String(message);
    }

    const remove = function() {
        item.classList.remove('show');
        setTimeout(function() { item.remove(); }, 220);
    };

    item.querySelector('.cb-toast-close').addEventListener('click', remove);
    stack.appendChild(item);
    requestAnimationFrame(function() { item.classList.add('show'); });
    if (duration > 0) {
        setTimeout(remove, duration);
    }
}

// 确认对话框
function confirmDialog(message, options) {
    options = options || {};
    const overlay = document.getElementById('cbConfirmOverlay');
    const titleNode = document.getElementById('cbConfirmTitle');
    const messageNode = document.getElementById('cbConfirmMessage');
    const okBtn = document.getElementById('cbConfirmOk');
    const cancelBtn = document.getElementById('cbConfirmCancel');

    if (!overlay || !titleNode || !messageNode || !okBtn || !cancelBtn) {
        return Promise.resolve(window.confirm(message));
    }

    return new Promise(function(resolve) {
        confirmQueue.push({
            message: message,
            options: options,
            resolve: resolve
        });
        showNextConfirm();
    });
}

function showNextConfirm() {
    if (activeConfirm || !confirmQueue.length) {
        return;
    }

    const overlay = document.getElementById('cbConfirmOverlay');
    const titleNode = document.getElementById('cbConfirmTitle');
    const messageNode = document.getElementById('cbConfirmMessage');
    const okBtn = document.getElementById('cbConfirmOk');
    const cancelBtn = document.getElementById('cbConfirmCancel');

    if (!overlay || !titleNode || !messageNode || !okBtn || !cancelBtn) {
        const next = confirmQueue.shift();
        next.resolve(window.confirm(next.message));
        showNextConfirm();
        return;
    }

    activeConfirm = confirmQueue.shift();
    const message = activeConfirm.message;
    const options = activeConfirm.options || {};
    titleNode.textContent = options.title || '请确认操作';
    messageNode.textContent = message;
    okBtn.textContent = options.okText || '确认';
    cancelBtn.textContent = options.cancelText || '取消';
    overlay.classList.add('show');
    confirmResolver = activeConfirm.resolve;
}

function resolveConfirm(result) {
    const overlay = document.getElementById('cbConfirmOverlay');
    if (overlay) overlay.classList.remove('show');
    if (confirmResolver) {
        confirmResolver(result);
        confirmResolver = null;
    }
    activeConfirm = null;
    setTimeout(showNextConfirm, 0);
}

// 兼容旧接口
function showToast(message, type, duration) {
    toast(message, type, duration);
}

function showConfirm(message, options) {
    return confirmDialog(message, options);
}

// 嵌入参数处理
function withEmbeddedParam(url) {
    try {
        const parsed = new URL(url, window.location.origin);
        parsed.searchParams.set('embedded', '1');
        return parsed.toString();
    } catch (e) {
        return url;
    }
}

function isMobileViewport() {
    return window.matchMedia && window.matchMedia('(max-width: 768px)').matches;
}

function closeMobileSidebar() {
    document.body.classList.remove('mobile-sidebar-open');
    var toggle = document.getElementById('mobileMenuToggle');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
}

function toggleMobileSidebar() {
    var shouldOpen = !document.body.classList.contains('mobile-sidebar-open');
    document.body.classList.toggle('mobile-sidebar-open', shouldOpen);
    var toggle = document.getElementById('mobileMenuToggle');
    if (toggle) toggle.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
    if (shouldOpen && typeof closeModuleMenus === 'function') closeModuleMenus();
}

// 子菜单切换
function toggleSubmenu(toggleEl) {
    var submenu = toggleEl.nextElementSibling;
    if (!submenu || !submenu.classList.contains('submenu-list')) return;
    var isOpen = submenu.classList.contains('open');
    if (isOpen) {
        submenu.classList.remove('open');
        toggleEl.setAttribute('aria-expanded', 'false');
    } else {
        submenu.classList.add('open');
        toggleEl.setAttribute('aria-expanded', 'true');
    }
}

// 多开菜单支持
function enableMultiOpenMenus() {
    // An iframe page belongs to the parent tab workspace. It must keep normal
    // in-frame navigation and must never create a second tab workspace.
    if (document.body.classList.contains('embedded-page')) return;

    const menuLinks = document.querySelectorAll('.sidebar a[href], .sidebar .dropdown-item[href]');
    menuLinks.forEach(function(link) {
        const href = link.getAttribute('href');
        if (!href || href === '#' || href.startsWith('javascript:') || link.dataset.multiOpenReady === 'true') {
            return;
        }

        link.dataset.multiOpenReady = 'true';
        link.classList.add('menu-multi-open');
        link.setAttribute('title', '左键正常打开；Ctrl/中键可同时新开标签页');

        const hasIcon = !!link.querySelector('i');
        const linkContent = link.innerHTML;
        link.innerHTML =
            '<span class="menu-link-main">' + linkContent + '</span>' +
            '<span class="menu-link-open-btn" role="button" tabindex="0" aria-label="新开页面" title="新开页面">' +
            '<i class="bi bi-box-arrow-up-right"></i></span>';

        const openBtn = link.querySelector('.menu-link-open-btn');
        if (hasIcon) {
            openBtn.classList.add('with-icon');
        }

        openBtn.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            window.open(href, '_blank', 'noopener');
        });

        openBtn.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                window.open(href, '_blank', 'noopener');
            }
        });

        link.addEventListener('auxclick', function(event) {
            if (event.button === 1) {
                window.open(href, '_blank', 'noopener');
            }
        });

        link.addEventListener('click', function(event) {
            if (isMobileViewport()) {
                closeMobileSidebar();
                return;
            }
            if (window.WmsTabs && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
                event.preventDefault();
                window.WmsTabs.open(href, link.textContent.trim());
                return;
            }
            if (event.ctrlKey || event.metaKey) {
                event.preventDefault();
                window.open(href, '_blank', 'noopener');
            }
        });
    });
}

// 标签页管理
window.WmsTabs = (function() {
    const tabs = new Map();
    let activeKey = '';

    function normalizeUrl(url) {
        const parsed = new URL(url, window.location.origin);
        parsed.searchParams.delete('embedded');
        const query = parsed.searchParams.toString();
        return parsed.pathname + (query ? '?' + query : '') + (parsed.hash || '');
    }

    function embeddedUrl(url) {
        try {
            const parsed = new URL(url, window.location.origin);
            parsed.searchParams.set('embedded', '1');
            return parsed.pathname + parsed.search + parsed.hash;
        } catch (e) {
            return url;
        }
    }

    function makeKey(url) {
        return normalizeUrl(url).replace(/[^a-zA-Z0-9_-]+/g, '_') || 'home';
    }

    function updateActiveMenu(url) {
        const targetPath = new URL(url, window.location.origin).pathname;
        document.querySelectorAll('.sidebar .nav-link, .sidebar .flyout-link').forEach(function(link) {
            const href = link.getAttribute('href');
            if (!href || href.startsWith('javascript:')) return;
            const linkPath = new URL(href, window.location.origin).pathname;
            link.classList.toggle('active', linkPath === targetPath);
        });
        document.querySelectorAll('.module-menu').forEach(function(menu) {
            const hasActive = !!menu.querySelector('.flyout-link.active');
            const toggle = menu.querySelector('.module-toggle');
            if (toggle) toggle.classList.toggle('active', hasActive);
        });
    }

    function persistTabs() {
        const data = Array.from(tabs.values()).map(function(tab) {
            return { key: tab.key, url: tab.url, title: tab.title };
        });
        localStorage.setItem('wms_open_tabs', JSON.stringify({ activeKey: activeKey, tabs: data }));
    }

    function activate(key) {
        if (!tabs.has(key)) return;
        activeKey = key;
        tabs.forEach(function(tab, tabKey) {
            const active = tabKey === key;
            tab.button.classList.toggle('active', active);
            tab.frame.classList.toggle('active', active);
        });
        updateActiveMenu(tabs.get(key).url);
        persistTabs();
    }

    function getActiveContext() {
        const tab = tabs.get(activeKey);
        return tab ? { key: tab.key, url: tab.url, title: tab.title } : null;
    }

    function close(key) {
        const tab = tabs.get(key);
        if (!tab) return;
        const keys = Array.from(tabs.keys());
        const index = keys.indexOf(key);
        tab.button.remove();
        tab.frame.remove();
        tabs.delete(key);
        if (activeKey === key) {
            const nextKey = keys[index + 1] || keys[index - 1] || '';
            if (nextKey) {
                activate(nextKey);
            } else {
                activeKey = '';
                persistTabs();
            }
        } else {
            persistTabs();
        }
    }

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

        const tabTitle = (title || normalizedUrl || '页面').replace(/\s+/g, ' ').trim();
        const button = document.createElement('div');
        button.className = 'tab-item';
        button.setAttribute('role', 'tab');
        button.innerHTML =
            '<span class="tab-title">' + tabTitle + '</span>' +
            '<button type="button" class="tab-close" aria-label="关闭"><i class="bi bi-x"></i></button>';

        const frame = document.createElement('iframe');
        frame.className = 'tab-frame';
        frame.src = embeddedUrl(normalizedUrl);

        button.addEventListener('click', function(event) {
            if (event.target.closest('.tab-close')) return;
            activate(key);
        });
        button.querySelector('.tab-close').addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            close(key);
        });

        tabs.set(key, { key: key, url: normalizedUrl, title: tabTitle, button: button, frame: frame });
        tabBar.appendChild(button);
        frameWrap.appendChild(frame);
        activate(key);
    }

    function restore() {
        if (!document.getElementById('tabBar')) return;
        const currentUrl = window.location.pathname + window.location.search + window.location.hash;
        const currentTitle = (window.location.pathname === '/' ? '首页' : document.title) || '页面';
        if (window.location.pathname === '/') {
            localStorage.removeItem('wms_open_tabs');
            open(currentUrl, currentTitle);
            return;
        }
        let restored = null;
        try {
            restored = JSON.parse(localStorage.getItem('wms_open_tabs') || 'null');
        } catch (error) {
            restored = null;
        }
        const savedTabs = Array.isArray(restored && restored.tabs) ? restored.tabs : [];
        savedTabs.slice(0, 8).forEach(function(tab) {
            if (tab.url && tab.title) open(tab.url, tab.title);
        });
        const currentKey = makeKey(currentUrl);
        if (tabs.has(currentKey)) {
            activate(currentKey);
        } else {
            open(currentUrl, currentTitle);
        }
    }

    return { open: open, close: close, activate: activate, restore: restore, getActiveContext: getActiveContext };
})();

// 下拉框刷新
window.WmsRefreshDropdowns = function(selectors) {
    var catSelects = document.querySelectorAll('[name="category_id"]');
    var unitSelects = document.querySelectorAll('[name="unit_id"]');
    var supSelects = document.querySelectorAll('[name="supplier_id"]');
    if (!catSelects.length && !unitSelects.length && !supSelects.length) return;
    Promise.all([
        fetch('/api/categories').then(function(r) { return r.json(); }).catch(function() { return []; }),
        fetch('/api/units').then(function(r) { return r.json(); }).catch(function() { return []; }),
        fetch('/api/suppliers').then(function(r) { return r.json(); }).catch(function() { return []; })
    ]).then(function(results) {
        var cats = results[0], units = results[1], sups = results[2];
        // 使用 createElement + textContent 构建 option，避免直接 innerHTML 拼接
        // 在分类/单位/供应商名包含 <、> 等字符时被解释为 HTML，造成下拉错乱或 XSS
        function refillSelect(sel, items) {
            var val = sel.value;
            while (sel.firstChild) { sel.removeChild(sel.firstChild); }
            var placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = '请选择';
            sel.appendChild(placeholder);
            items.forEach(function(item) {
                var opt = document.createElement('option');
                opt.value = item.id;
                opt.textContent = item.name;
                sel.appendChild(opt);
            });
            sel.value = val;
        }
        catSelects.forEach(function(sel) { refillSelect(sel, cats); });
        unitSelects.forEach(function(sel) { refillSelect(sel, units); });
        supSelects.forEach(function(sel) { refillSelect(sel, sups); });
    });
};

// 可调整表格
function setupResizableTable(config) {
    config = config || {};
    const table = typeof config.tableSelector === 'string'
        ? document.querySelector(config.tableSelector)
        : config.tableSelector;
    if (!table || table.dataset.colResizeReady === 'true') return null;

    const headerCells = Array.from(table.querySelectorAll('thead th'));
    if (!headerCells.length) return null;

    const storageKey = config.storageKey || 'cb_resizable_table_' + (config.tableId || table.id || window.location.pathname);
    const excludedColumns = new Set(config.excludeColumns || []);
    const minWidth = config.minWidth || 60;
    const enableColumnReorder = config.enableColumnReorder !== false;
    let state = { widths: {}, columnOrder: [] };

    try {
        const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
        state = { widths: {}, columnOrder: [], ...saved };
    } catch (error) {
        state = { widths: {}, columnOrder: [] };
    }

    const persistState = function() {
        localStorage.setItem(storageKey, JSON.stringify(state));
    };

    const columns = headerCells.map(function(th, index) {
        const key = th.dataset.columnKey || th.textContent.trim() || 'column_' + index;
        th.dataset.columnKey = key;
        return { index: index, key: key, th: th, excluded: excludedColumns.has(key) };
    });

    const getColumnMinWidth = function(column) {
        const th = column && column.th;
        const key = String((column && column.key) || '').trim();
        if (th && th.classList.contains('action-col')) return 92;
        if (th && th.classList.contains('row-num')) return 42;
        if (/^(操作|动作|Action)$/i.test(key)) return 92;
        if (/^(序号|行号|#)$/i.test(key)) return 42;
        return minWidth;
    };

    const applyColumnOrder = function() {
        if (!state.columnOrder || state.columnOrder.length === 0) return;
        const theadRow = table.querySelector('thead tr');
        if (!theadRow) return;
        const ths = Array.from(theadRow.querySelectorAll('th'));
        const ordered = [];
        const remaining = [];
        state.columnOrder.forEach(function(key) {
            const th = ths.find(function(t) { return t.dataset.columnKey === key; });
            if (th) ordered.push(th);
        });
        ths.forEach(function(th) {
            if (ordered.indexOf(th) === -1) remaining.push(th);
        });
        const finalOrder = ordered.concat(remaining);
        const frag = document.createDocumentFragment();
        finalOrder.forEach(function(th) { frag.appendChild(th); });
        theadRow.appendChild(frag);
        const rows = table.querySelectorAll('tbody tr');
        const rowFrags = [];
        rows.forEach(function(row) {
            const cells = Array.from(row.querySelectorAll('td'));
            const cellMap = {};
            finalOrder.forEach(function(th, idx) {
                const key = th.dataset.columnKey;
                if (cells[idx]) cellMap[key] = cells[idx];
            });
            const rowFrag = document.createDocumentFragment();
            finalOrder.forEach(function(th) {
                const key = th.dataset.columnKey;
                if (cellMap[key]) rowFrag.appendChild(cellMap[key]);
            });
            rowFrags.push({ row: row, frag: rowFrag });
        });
        rowFrags.forEach(function(item) { item.row.appendChild(item.frag); });
        ensureColgroup();
    };

    const ensureColgroup = function() {
        let colgroup = table.querySelector('colgroup');
        if (!colgroup) {
            colgroup = document.createElement('colgroup');
            const colCount = headerCells.length;
            for (let i = 0; i < colCount; i++) {
                const col = document.createElement('col');
                colgroup.appendChild(col);
            }
            table.insertBefore(colgroup, table.firstChild);
        }
        return colgroup;
    };

    const applyWidths = function() {
        const colgroup = ensureColgroup();
        const cols = Array.from(colgroup.querySelectorAll('col'));
        columns.forEach(function(column) {
            let width = state.widths && state.widths[column.key];
            const columnMinWidth = getColumnMinWidth(column);
            if (width && width < columnMinWidth) {
                width = columnMinWidth;
                state.widths[column.key] = width;
            }
            const col = cols[column.index];
            if (!col) return;
            if (width) {
                col.style.width = width + 'px';
                column.th.style.width = width + 'px';
                column.th.style.minWidth = columnMinWidth + 'px';
                col.style.minWidth = columnMinWidth + 'px';
            } else {
                col.style.width = '';
                column.th.style.width = '';
                column.th.style.minWidth = columnMinWidth + 'px';
                col.style.minWidth = columnMinWidth + 'px';
            }
        });
    };

    table.classList.add('cb-resizable-table');
    table.dataset.colResizeReady = 'true';
    table.style.setProperty('table-layout', 'fixed', 'important');

    // 列拖拽重排
    let dragColumn = null;
    let dragOverColumn = null;

    if (enableColumnReorder) {
        headerCells.forEach(function(th) {
            if (th.querySelector(':scope > .cb-col-resizer')) return;
            const key = th.dataset.columnKey;
            if (excludedColumns.has(key)) return;

            th.setAttribute('draggable', 'true');
            th.style.cursor = 'grab';

            th.addEventListener('dragstart', function(e) {
                dragColumn = this;
                this.style.opacity = '0.5';
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', key);
            });

            th.addEventListener('dragend', function() {
                this.style.opacity = '1';
                dragColumn = null;
                dragOverColumn = null;
                document.querySelectorAll('.cb-col-drag-over').forEach(function(el) { el.classList.remove('cb-col-drag-over'); });
            });

            th.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                if (dragColumn && dragColumn !== this) {
                    document.querySelectorAll('.cb-col-drag-over').forEach(function(el) { el.classList.remove('cb-col-drag-over'); });
                    this.classList.add('cb-col-drag-over');
                    dragOverColumn = this;
                }
            });

            th.addEventListener('dragleave', function() {
                this.classList.remove('cb-col-drag-over');
            });

            th.addEventListener('drop', function(e) {
                e.preventDefault();
                this.classList.remove('cb-col-drag-over');
                if (!dragColumn || dragColumn === this) return;

                const theadRow = table.querySelector('thead tr');
                const allThs = Array.from(theadRow.querySelectorAll('th'));
                const fromIndex = allThs.indexOf(dragColumn);
                const toIndex = allThs.indexOf(this);

                if (fromIndex < toIndex) {
                    theadRow.insertBefore(dragColumn, this.nextSibling);
                } else {
                    theadRow.insertBefore(dragColumn, this);
                }

                const rows = Array.from(table.querySelectorAll('tbody tr'));
                rows.forEach(function(row) {
                    const cells = Array.from(row.querySelectorAll('td'));
                    if (cells[fromIndex] && cells[toIndex]) {
                        const dragCell = cells[fromIndex];
                        const targetCell = cells[toIndex];
                        if (fromIndex < toIndex) {
                            row.insertBefore(dragCell, targetCell.nextSibling);
                        } else {
                            row.insertBefore(dragCell, targetCell);
                        }
                    }
                });

                const newOrder = Array.from(theadRow.querySelectorAll('th')).map(function(th) { return th.dataset.columnKey; });
                state.columnOrder = newOrder;
                persistState();
            });
        });
    }

    // 添加拖拽样式
    if (!document.getElementById('cb-col-drag-style')) {
        const style = document.createElement('style');
        style.id = 'cb-col-drag-style';
        style.textContent =
            '.cb-resizable-table th[draggable="true"] { cursor: grab !important; position: relative; user-select: none; }' +
            '.cb-resizable-table th[draggable="true"]:hover { background: #e9ecef !important; }' +
            '.cb-resizable-table th[draggable="true"]:active { cursor: grabbing !important; }' +
            '.cb-resizable-table th[draggable="true"]::before { content: "\\2807"; position: absolute; right: 4px; top: 50%; transform: translateY(-50%); color: #adb5bd; font-size: 14px; pointer-events: none; opacity: 0; transition: opacity 0.2s; }' +
            '.cb-resizable-table th[draggable="true"]:hover::before { opacity: 1; }' +
            '.cb-col-drag-over { border-left: 3px solid #0d6efd !important; position: relative; }' +
            '.cb-col-drag-over::after { content: ""; position: absolute; left: -3px; top: 0; bottom: 0; width: 3px; background: #0d6efd; }';
        document.head.appendChild(style);
    }

    if (enableColumnReorder && state.columnOrder && state.columnOrder.length > 0) {
        applyColumnOrder();
    }

    columns.forEach(function(column) {
        if (column.excluded) return;
        if (column.th.querySelector(':scope > .cb-col-resizer')) return;

        const resizer = document.createElement('span');
        resizer.className = 'cb-col-resizer';
        column.th.appendChild(resizer);

        resizer.addEventListener('mousedown', function(event) {
            event.preventDefault();
            event.stopPropagation();
            const startX = event.clientX;
            const startWidth = column.th.getBoundingClientRect().width;
            document.body.classList.add('cb-col-resize-active');

            const onMouseMove = function(moveEvent) {
                const nextWidth = Math.max(getColumnMinWidth(column), startWidth + moveEvent.clientX - startX);
                state.widths = state.widths || {};
                state.widths[column.key] = Math.round(nextWidth);
                applyWidths();
            };

            const onMouseUp = function() {
                document.body.classList.remove('cb-col-resize-active');
                persistState();
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
            };

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
    });

    applyWidths();
    return {
        applyWidths: applyWidths,
        reset: function() {
            state = { widths: {}, columnOrder: [] };
            persistState();
            applyWidths();
        }
    };
}

// 动态明细表字段位置和列宽控制
function setupDynamicDetailColumnControls(config) {
    config = config || {};
    const table = typeof config.tableSelector === 'string'
        ? document.querySelector(config.tableSelector)
        : config.tableSelector;
    if (!table || table.dataset.dynamicDetailColumnsReady === 'true') return null;

    const headerRow = table.querySelector('thead tr');
    if (!headerRow) return null;

    table.dataset.dynamicDetailColumnsReady = 'true';
    table.dataset.colResizeReady = 'true';
    table.classList.add('wms-detail-column-table');

    const orderKey = config.orderKey || 'wms_detail_column_order_' + (table.id || window.location.pathname);
    const widthKey = config.widthKey || 'wms_detail_column_widths_' + (table.id || window.location.pathname);
    const lockedColumns = new Set(config.lockedColumns || []);
    const minWidths = config.minWidths || {};
    const defaultHeaderCells = Array.from(headerRow.children);
    const defaultOrder = defaultHeaderCells.map(function(cell, index) {
        const key = cell.dataset.columnKey || 'column_' + index;
        cell.dataset.columnKey = key;
        return key;
    });
    const initialWidths = {};
    defaultHeaderCells.forEach(function(cell) {
        initialWidths[cell.dataset.columnKey] = cell.style.width || '';
    });

    const readJson = function(key, fallback) {
        try {
            const value = JSON.parse(localStorage.getItem(key) || 'null');
            return value == null ? fallback : value;
        } catch (error) {
            return fallback;
        }
    };

    const getMinWidth = function(cellOrKey) {
        const key = typeof cellOrKey === 'string' ? cellOrKey : (cellOrKey && cellOrKey.dataset.columnKey);
        const cell = typeof cellOrKey === 'string'
            ? table.querySelector('thead th[data-column-key="' + CSS.escape(cellOrKey) + '"]')
            : cellOrKey;
        if (minWidths[key]) return minWidths[key];
        if (cell && cell.classList.contains('action-col')) return 92;
        if (cell && cell.classList.contains('row-num')) return 42;
        if (key === 'actions') return 92;
        if (key === 'row_no') return 42;
        return config.minWidth || 60;
    };

    const normalizeOrder = function(order) {
        const input = Array.isArray(order) ? order : [];
        const valid = input.filter(function(key, index) {
            return defaultOrder.indexOf(key) !== -1 && input.indexOf(key) === index;
        });
        const movableDefaults = defaultOrder.filter(function(key) { return !lockedColumns.has(key); });
        const movable = valid.filter(function(key) { return !lockedColumns.has(key); });
        movableDefaults.forEach(function(key) {
            if (movable.indexOf(key) === -1) movable.push(key);
        });
        const movableQueue = movable.slice();
        return defaultOrder.map(function(key) {
            return lockedColumns.has(key) ? key : movableQueue.shift();
        }).filter(Boolean);
    };

    const getCurrentOrder = function() {
        return Array.from(headerRow.children).map(function(cell) {
            return cell.dataset.columnKey;
        }).filter(Boolean);
    };

    const saveOrder = function(order) {
        localStorage.setItem(orderKey, JSON.stringify(normalizeOrder(order)));
    };

    const reorderRow = function(row, order) {
        if (!row) return;
        const cells = Array.from(row.children);
        const byKey = new Map();
        cells.forEach(function(cell) {
            const key = cell.dataset.columnKey;
            if (key) byKey.set(key, cell);
        });
        if (!byKey.size) return;
        const frag = document.createDocumentFragment();
        order.forEach(function(key) {
            const cell = byKey.get(key);
            if (cell) frag.appendChild(cell);
        });
        cells.forEach(function(cell) {
            const key = cell.dataset.columnKey;
            if (!key || order.indexOf(key) === -1) {
                frag.appendChild(cell);
            }
        });
        row.appendChild(frag);
    };

    const syncFooterLabel = function() {
        const footerRow = table.querySelector('tfoot tr[data-total-row="true"]');
        if (!footerRow) return;
        const labelHtml = footerRow.dataset.totalLabel || '<strong>合计：</strong>';
        Array.from(footerRow.children).forEach(function(cell) {
            if (cell.dataset.totalLabelCell === 'true') {
                cell.innerHTML = '';
                cell.classList.remove('text-end');
                delete cell.dataset.totalLabelCell;
            }
        });
        const cells = Array.from(footerRow.children);
        const amountIndex = cells.findIndex(function(cell) {
            return cell.dataset.columnKey === 'amount';
        });
        const labelCell = cells[amountIndex > 0 ? amountIndex - 1 : 0];
        if (labelCell && labelCell.dataset.columnKey !== 'amount') {
            labelCell.innerHTML = labelHtml;
            labelCell.classList.add('text-end');
            labelCell.dataset.totalLabelCell = 'true';
        }
    };

    const applyWidths = function() {
        const widths = readJson(widthKey, {});
        Array.from(headerRow.children).forEach(function(th) {
            const key = th.dataset.columnKey;
            const minWidth = getMinWidth(th);
            const width = parseFloat(widths[key]);
            if (Number.isFinite(width) && width > 0) {
                const normalizedWidth = Math.max(minWidth, width);
                th.style.width = normalizedWidth + 'px';
                th.style.minWidth = normalizedWidth + 'px';
            } else {
                th.style.width = initialWidths[key] || '';
                th.style.minWidth = minWidth + 'px';
            }
        });
    };

    const applyOrder = function() {
        const savedOrder = normalizeOrder(readJson(orderKey, defaultOrder));
        reorderRow(headerRow, savedOrder);
        table.querySelectorAll('tbody tr, tfoot tr').forEach(function(row) {
            reorderRow(row, savedOrder);
        });
        syncFooterLabel();
        applyWidths();
    };

    const persistCurrentWidths = function() {
        const widths = {};
        Array.from(headerRow.children).forEach(function(th) {
            const key = th.dataset.columnKey;
            if (key) widths[key] = Math.round(th.getBoundingClientRect().width || th.offsetWidth || 0);
        });
        localStorage.setItem(widthKey, JSON.stringify(widths));
    };

    let draggedKey = null;
    const setupHeaderDrag = function() {
        Array.from(headerRow.children).forEach(function(th) {
            const key = th.dataset.columnKey;
            if (!key || lockedColumns.has(key)) return;
            th.draggable = true;
            th.classList.add('detail-col-draggable');
            th.title = th.title || '拖动表头调整字段位置，拖动右侧边线调整宽度';

            th.addEventListener('dragstart', function(event) {
                if (event.target.closest('.col-resize')) {
                    event.preventDefault();
                    return;
                }
                draggedKey = key;
                th.dataset.dragging = 'true';
                th.classList.add('detail-col-dragging');
                event.dataTransfer.effectAllowed = 'move';
                event.dataTransfer.setData('text/plain', key);
            });

            th.addEventListener('dragend', function() {
                draggedKey = null;
                th.classList.remove('detail-col-dragging');
                setTimeout(function() {
                    th.dataset.dragging = 'false';
                }, 0);
                table.querySelectorAll('.detail-col-drag-over').forEach(function(cell) {
                    cell.classList.remove('detail-col-drag-over');
                });
            });

            th.addEventListener('dragover', function(event) {
                if (!draggedKey || draggedKey === key || lockedColumns.has(key)) return;
                event.preventDefault();
                event.dataTransfer.dropEffect = 'move';
                table.querySelectorAll('.detail-col-drag-over').forEach(function(cell) {
                    cell.classList.remove('detail-col-drag-over');
                });
                th.classList.add('detail-col-drag-over');
            });

            th.addEventListener('dragleave', function() {
                th.classList.remove('detail-col-drag-over');
            });

            th.addEventListener('drop', function(event) {
                event.preventDefault();
                th.classList.remove('detail-col-drag-over');
                if (!draggedKey || draggedKey === key || lockedColumns.has(key)) return;
                const currentOrder = getCurrentOrder();
                const fromIndex = currentOrder.indexOf(draggedKey);
                const toIndex = currentOrder.indexOf(key);
                if (fromIndex === -1 || toIndex === -1) return;
                const nextOrder = currentOrder.filter(function(item) { return item !== draggedKey; });
                const targetIndex = nextOrder.indexOf(key);
                nextOrder.splice(fromIndex < toIndex ? targetIndex + 1 : targetIndex, 0, draggedKey);
                saveOrder(nextOrder);
                applyOrder();
            });
        });
    };

    const setupResize = function() {
        table.querySelectorAll('thead th .col-resize').forEach(function(resizer) {
            if (resizer.dataset.dynamicResizeReady === 'true') return;
            resizer.dataset.dynamicResizeReady = 'true';
            resizer.addEventListener('mousedown', function(event) {
                event.preventDefault();
                event.stopPropagation();
                const th = resizer.closest('th');
                const key = th && th.dataset.columnKey;
                if (!th || !key) return;
                const startX = event.pageX;
                const startWidth = th.getBoundingClientRect().width || th.offsetWidth;
                const minWidth = getMinWidth(th);
                resizer.classList.add('active');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';

                const onMove = function(moveEvent) {
                    const nextWidth = Math.max(minWidth, startWidth + moveEvent.pageX - startX);
                    th.style.width = nextWidth + 'px';
                    th.style.minWidth = nextWidth + 'px';
                };

                const onUp = function() {
                    resizer.classList.remove('active');
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';
                    persistCurrentWidths();
                    document.removeEventListener('mousemove', onMove);
                    document.removeEventListener('mouseup', onUp);
                };

                document.addEventListener('mousemove', onMove);
                document.addEventListener('mouseup', onUp);
            });
        });
    };

    if (!document.getElementById('wms-detail-column-style')) {
        const style = document.createElement('style');
        style.id = 'wms-detail-column-style';
        style.textContent =
            '.wms-detail-column-table th{position:relative;}' +
            '.wms-detail-column-table th.detail-col-draggable{cursor:grab!important;user-select:none;}' +
            '.wms-detail-column-table th.detail-col-draggable:active{cursor:grabbing!important;}' +
            '.wms-detail-column-table th.detail-col-draggable::before{content:"\\2807";position:absolute;left:3px;top:50%;transform:translateY(-50%);color:#8c8c8c;font-size:13px;opacity:0;pointer-events:none;}' +
            '.wms-detail-column-table th.detail-col-draggable:hover::before{opacity:1;}' +
            '.wms-detail-column-table th.detail-col-dragging{opacity:.55;}' +
            '.wms-detail-column-table th.detail-col-drag-over{box-shadow:inset 3px 0 0 #1890ff!important;background:#e6f7ff!important;}' +
            '.wms-detail-column-table .col-resize{position:absolute;right:0;top:0;width:5px;height:100%;cursor:col-resize;z-index:5;}' +
            '.wms-detail-column-table .col-resize:hover,.wms-detail-column-table .col-resize.active{background:#1890ff;}';
        document.head.appendChild(style);
    }

    setupHeaderDrag();
    setupResize();
    applyOrder();

    return {
        applyOrder: applyOrder,
        applyWidths: applyWidths,
        setOrder: function(order) {
            saveOrder(order);
            applyOrder();
        },
        reset: function() {
            localStorage.removeItem(orderKey);
            localStorage.removeItem(widthKey);
            applyOrder();
        }
    };
}

function autoSetupResizableTables() {
    const pageScope = document.querySelector('.embedded-content') || document;
    const tables = pageScope.querySelectorAll('table');
    tables.forEach(function(table, index) {
        if (!table.querySelector('thead th')) return;
        if (table.dataset.enhanced === 'true') return;
        if (table.dataset.colResizeReady === 'true') return;
        if (table.dataset.disableAutoResize === 'true') return;
        if (table.closest('.modal')) return;
        if (table.closest('.label-canvas, .fabric-container, .tox, .tox-editor-container, .print-page')) return;
        if (table.matches('.label-table, .print-table, .mini-table') || table.id === 'labelTable') return;

        const pageKey = document.body.dataset.pageKey || window.location.pathname || 'page';
        const tableKey = table.id || 'auto_table_' + index;
        setupResizableTable({
            tableSelector: table,
            tableId: pageKey + '_' + tableKey,
            minWidth: 70,
            enableColumnReorder: false
        });
    });
}

// 明细表增强
function setupDetailTable(config) {
    config = config || {};
    const defaultState = {
        search: '',
        sortKey: '',
        sortDirection: 'asc',
        hiddenColumns: [],
        widths: {}
    };

    let state = Object.assign({}, defaultState);
    try {
        state = Object.assign({}, defaultState, JSON.parse(localStorage.getItem(config.storageKey) || '{}'));
    } catch (error) {
        state = Object.assign({}, defaultState);
    }

    const persistState = function() {
        localStorage.setItem(config.storageKey, JSON.stringify(state));
    };

    const table = typeof config.tableSelector === 'string'
        ? document.querySelector(config.tableSelector)
        : config.tableSelector;
    if (!table) return null;

    table.classList.add('cb-detail-table-enhanced');
    table.dataset.enhanced = 'true';

    const headerCells = Array.from(table.querySelectorAll('thead th'));
    const tbody = table.querySelector('tbody');
    if (!tbody) return null;
    const allRows = Array.from(tbody.querySelectorAll('tr'));
    const staticRows = allRows.filter(function(row) { return row.dataset.static === 'true'; });
    const dataRows = allRows.filter(function(row) { return row.dataset.static !== 'true'; });

    const wrapper = table.closest('.table-responsive, .table-responsive-wrapper') || table.parentElement;
    const hostCard = table.closest('.card');
    if (!wrapper || !hostCard) return null;

    const excludedColumns = new Set(config.excludeColumns || []);
    const sortableColumns = config.sortableColumns || [];
    const searchableColumns = config.searchableColumns || [];
    const columnLabels = config.columnLabels || {};

    const toolbar = document.createElement('div');
    toolbar.className = 'cb-detail-toolbar';
    toolbar.innerHTML =
        '<div class="cb-detail-toolbar-left">' +
        '<div class="input-group input-group-sm cb-detail-search">' +
        '<span class="input-group-text"><i class="bi bi-search"></i></span>' +
        '<input type="text" class="form-control" placeholder="搜索明细字段内容">' +
        '</div><span class="cb-detail-count"></span></div>' +
        '<div class="cb-detail-toolbar-right">' +
        '<div class="position-relative">' +
        '<button type="button" class="btn btn-sm btn-outline-secondary cb-column-toggle-btn">' +
        '<i class="bi bi-layout-three-columns"></i> 自定义字段</button>' +
        '<div class="cb-column-panel"><div class="cb-column-panel-title">选择显示字段</div>' +
        '<div class="cb-column-options"></div></div></div>' +
        '<button type="button" class="btn btn-sm btn-outline-secondary cb-reset-table-btn">' +
        '<i class="bi bi-arrow-counterclockwise"></i> 重置</button></div>';

    hostCard.insertBefore(toolbar, wrapper);

    const searchInput = toolbar.querySelector('.cb-detail-search input');
    const countNode = toolbar.querySelector('.cb-detail-count');
    const columnBtn = toolbar.querySelector('.cb-column-toggle-btn');
    const columnPanel = toolbar.querySelector('.cb-column-panel');
    const columnOptionsNode = toolbar.querySelector('.cb-column-options');
    const resetBtn = toolbar.querySelector('.cb-reset-table-btn');

    const columns = headerCells.map(function(th, index) {
        const key = th.dataset.columnKey || th.textContent.trim() || 'column_' + index;
        th.dataset.columnKey = key;
        return {
            index: index,
            key: key,
            label: columnLabels[key] || th.textContent.trim() || '字段' + (index + 1),
            th: th,
            excluded: excludedColumns.has(key)
        };
    });

    const getCellText = function(row, columnIndex) {
        const cell = row.children[columnIndex];
        return cell ? cell.textContent.trim() : '';
    };

    const normalizeForCompare = function(value) {
        if (value == null) return '';
        return String(value).replace(/[¥,]/g, '').trim();
    };

    const compareValues = function(a, b) {
        const normalizedA = normalizeForCompare(a);
        const normalizedB = normalizeForCompare(b);
        const numA = parseFloat(normalizedA);
        const numB = parseFloat(normalizedB);
        if (!Number.isNaN(numA) && !Number.isNaN(numB)) {
            return numA - numB;
        }
        return normalizedA.localeCompare(normalizedB, 'zh-CN');
    };

    const updateCount = function() {
        const visibleRows = dataRows.filter(function(row) { return !row.classList.contains('cb-row-hidden'); }).length;
        countNode.textContent = '已显示 ' + visibleRows + ' / ' + dataRows.length + ' 条明细';
    };

    const applyColumnVisibility = function() {
        const hidden = new Set(state.hiddenColumns || []);
        columns.forEach(function(column) {
            const hiddenColumn = hidden.has(column.key);
            if (column.excluded) return;
            column.th.classList.toggle('cb-detail-hidden', hiddenColumn);
            Array.from(table.querySelectorAll('tr')).forEach(function(row) {
                const cell = row.children[column.index];
                if (cell) {
                    cell.classList.toggle('cb-detail-hidden', hiddenColumn);
                }
            });
        });
    };

    const filterRows = function() {
        const keyword = (state.search || '').trim().toLowerCase();
        dataRows.forEach(function(row) {
            const rowText = searchableColumns.length
                ? searchableColumns.map(function(key) {
                    const column = columns.find(function(item) { return item.key === key; });
                    return column ? getCellText(row, column.index) : '';
                }).join(' ')
                : row.textContent;
            const matched = !keyword || rowText.toLowerCase().includes(keyword);
            row.classList.toggle('cb-row-hidden', !matched);
        });
        updateCount();
    };

    const applySortIndicators = function() {
        columns.forEach(function(column) {
            column.th.classList.remove('sorted-asc', 'sorted-desc', 'cb-detail-sortable');
            const existingIndicator = column.th.querySelector('.cb-sort-indicator');
            if (existingIndicator) existingIndicator.remove();
            if (sortableColumns.indexOf(column.key) !== -1) {
                column.th.classList.add('cb-detail-sortable');
                const indicator = document.createElement('span');
                indicator.className = 'cb-sort-indicator';
                indicator.innerHTML = '<i class="bi bi-arrow-down-up"></i>';
                column.th.appendChild(indicator);
                if (state.sortKey === column.key) {
                    column.th.classList.add(state.sortDirection === 'asc' ? 'sorted-asc' : 'sorted-desc');
                    indicator.innerHTML = state.sortDirection === 'asc'
                        ? '<i class="bi bi-sort-down"></i>'
                        : '<i class="bi bi-sort-up"></i>';
                }
            }
        });
    };

    const sortRows = function() {
        if (!state.sortKey) return;
        const targetColumn = columns.find(function(column) { return column.key === state.sortKey; });
        if (!targetColumn) return;
        dataRows.sort(function(rowA, rowB) {
            const result = compareValues(getCellText(rowA, targetColumn.index), getCellText(rowB, targetColumn.index));
            return state.sortDirection === 'asc' ? result : -result;
        });
        const anchorRow = staticRows.length ? staticRows[0] : null;
        dataRows.forEach(function(row) { tbody.insertBefore(row, anchorRow); });
    };

    const buildColumnOptions = function() {
        columnOptionsNode.innerHTML = '';
        columns.filter(function(column) { return !column.excluded; }).forEach(function(column) {
            const option = document.createElement('label');
            option.className = 'cb-column-option';
            option.innerHTML = '<input type="checkbox" class="form-check-input" data-column-key="' + column.key + '"><span>' + column.label + '</span>';
            const checkbox = option.querySelector('input');
            checkbox.checked = (state.hiddenColumns || []).indexOf(column.key) === -1;
            checkbox.addEventListener('change', function() {
                if (!this.checked) {
                    state.hiddenColumns = Array.from(new Set((state.hiddenColumns || []).concat(column.key)));
                } else {
                    state.hiddenColumns = (state.hiddenColumns || []).filter(function(key) { return key !== column.key; });
                }
                persistState();
                applyColumnVisibility();
            });
            columnOptionsNode.appendChild(option);
        });
    };

    const rerender = function() {
        sortRows();
        filterRows();
        applySortIndicators();
        applyColumnVisibility();
    };

    searchInput.value = state.search || '';
    searchInput.addEventListener('input', function() {
        state.search = this.value;
        persistState();
        filterRows();
    });

    columnBtn.addEventListener('click', function(event) {
        event.stopPropagation();
        columnPanel.classList.toggle('show');
    });

    if (setupDetailTable._columnPanelClickHandler) {
        document.removeEventListener('click', setupDetailTable._columnPanelClickHandler);
    }
    setupDetailTable._columnPanelClickHandler = function(event) {
        if (!columnPanel.contains(event.target) && !columnBtn.contains(event.target)) {
            columnPanel.classList.remove('show');
        }
    };
    document.addEventListener('click', setupDetailTable._columnPanelClickHandler);

    resetBtn.addEventListener('click', function() {
        state = Object.assign({}, defaultState);
        persistState();
        searchInput.value = '';
        buildColumnOptions();
        rerender();
        showToast('明细表设置已重置', 'success', 1800);
    });

    columns.forEach(function(column) {
        if (sortableColumns.indexOf(column.key) !== -1) {
            column.th.addEventListener('click', function(event) {
                if (event.target.closest('.cb-col-resizer')) return;
                state.sortDirection = state.sortKey === column.key && state.sortDirection === 'asc' ? 'desc' : 'asc';
                state.sortKey = column.key;
                persistState();
                rerender();
            });
        }
    });

    buildColumnOptions();
    rerender();
    return { rerender: rerender };
}

// 全选功能
function initCheckAll(tableId) {
    var table = document.getElementById(tableId);
    if (!table) return;

    var checkAll = table.querySelector('#checkAll');
    var checkItems = table.querySelectorAll('.check-item');

    if (!checkAll || checkItems.length === 0) return;

    checkAll.addEventListener('change', function() {
        checkItems.forEach(function(item) {
            if (item.disabled) return;
            item.checked = checkAll.checked;
        });
    });

    checkItems.forEach(function(item) {
        item.addEventListener('change', function() {
            var enabledItems = Array.from(checkItems).filter(function(i) { return !i.disabled; });
            var allChecked = enabledItems.length > 0 && enabledItems.every(function(i) { return i.checked; });
            var someChecked = enabledItems.some(function(i) { return i.checked; });
            checkAll.checked = allChecked;
            checkAll.indeterminate = someChecked && !allChecked;
        });
    });
}

// 批量删除
function batchDelete(url, tableId) {
    var checkedItems = document.querySelectorAll('#' + tableId + ' .check-item:checked');
    if (checkedItems.length === 0) {
        alert('请选择要删除的项');
        return;
    }
    if (!confirm('确定要删除选中的 ' + checkedItems.length + ' 项吗？')) return;

    var ids = Array.from(checkedItems).map(function(item) { return item.value; });
    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: ids })
    })
    .then(function(response) { return response.json(); })
    .then(function(res) {
        if (res.status === 'success') {
            location.reload();
        } else {
            alert(res.msg || '操作失败');
        }
    })
    .catch(function(error) {
        alert('操作失败：' + error.message);
    });
}

function setupSortableHeaders() {
    document.querySelectorAll('.sortable-header[data-sortable]').forEach(function(th) {
        if (th.dataset.sortReady === 'true') return;
        th.dataset.sortReady = 'true';
        th.addEventListener('click', function() {
            var sortField = this.dataset.sortable;
            if (!sortField) return;
            var url = new URL(window.location.href);
            var currentSort = url.searchParams.get('sort') || '';
            var currentOrder = url.searchParams.get('order') || 'desc';
            var newOrder = (currentSort === sortField && currentOrder === 'asc') ? 'desc' : 'asc';
            url.searchParams.set('sort', sortField);
            url.searchParams.set('order', newOrder);
            url.searchParams.set('page', '1');
            window.location.href = url.toString();
        });
    });
}

// 单个删除
async function deleteItem(url, id) {
    const confirmed = await showConfirm('确定要删除吗？', { title: '删除确认' });
    if (!confirmed) return;
    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: [id] })
    })
    .then(function(response) { return response.json(); })
    .then(function(res) {
        if (res.status === 'success') {
            showToast(res.msg || '删除成功', 'success');
            setTimeout(function() { location.reload(); }, 600);
        } else {
            showToast(res.msg || '删除失败', 'danger', 3600);
        }
    })
    .catch(function(error) {
        showToast('删除失败：' + error.message, 'danger', 3600);
    });
}

const WMS_ACTION_MODULES = {
    in_order: {
        match: /^\/in_order(\/?$|\/add|\/\d+)/,
        navigator: true,
        detailUrl: '/in_order/{id}',
        addUrl: '/in_order/add',
        listUrl: '/in_order',
        tableId: 'inOrderTable',
        deleteUrl: '/in_order/batch_delete',
        detailDeleteUrl: '/in_order/{id}/delete',
        detailPrintUrl: '/in_order/{id}/print',
        detailExportUrl: '/in_order/{id}/export',
        exportUrl: '/in_order/export',
        importUrl: '/import/in_order',
        templateUrl: '/export/template/in_order',
        printTemplateUrl: '/in_order_print_template',
        printListUrl: '/report/inout/print'
    },
    out_order: {
        match: /^\/out_order(\/?$|\/add|\/\d+)/,
        navigator: true,
        detailUrl: '/out_order/{id}',
        addUrl: '/out_order/add',
        listUrl: '/out_order',
        tableId: 'outOrderTable',
        deleteUrl: '/out_order/batch_delete',
        detailDeleteUrl: '/out_order/{id}/delete',
        detailPrintUrl: '/out_order/{id}/print',
        detailExportUrl: '/out_order/{id}/export',
        exportUrl: '/out_order/export',
        importUrl: '/import/out_order',
        templateUrl: '/export/template/out_order',
        printTemplateUrl: '/out_order_print_template',
        printListUrl: '/report/inout/print'
    },
    after_sale_out: {
        match: /^\/after_sale_out(\/?$|\/add|\/\d+)/,
        navigator: true,
        detailUrl: '/after_sale_out/{id}',
        addUrl: '/after_sale_out/add',
        listUrl: '/after_sale_out',
        tableId: 'afterSaleOutTable',
        deleteUrl: '/after_sale_out/batch_delete',
        detailDeleteUrl: '/after_sale_out/{id}/delete',
        exportUrl: '/export/after_sale_out',
        importUrl: '/after_sale_out/import',
        templateUrl: '/export/template/after_sale_out'
    },
    purchase_request: {
        match: /^\/purchase_request(\/?$|\/add|\/\d+)/,
        navigator: true,
        detailUrl: '/purchase_request/{id}',
        addUrl: '/purchase_request/add',
        listUrl: '/purchase_request',
        tableId: 'purchaseRequestTable',
        deleteUrl: '/purchase_request/batch_delete',
        detailDeleteUrl: '/purchase_request/{id}/delete',
        exportUrl: '/purchase_request/export',
        importUrl: '/purchase_request/import',
        templateUrl: '/export/template/purchase_request'
    },
    purchase_order: {
        match: /^\/purchase_order(\/?$|\/add|\/\d+|\/\d+\/edit)/,
        navigator: true,
        detailUrl: '/purchase_order/{id}',
        addUrl: '/purchase_order/add',
        listUrl: '/purchase_order',
        tableId: 'purchaseOrderTable',
        deleteUrl: '/purchase_order/batch_delete',
        detailDeleteUrl: '/purchase_order/{id}/delete',
        detailPrintUrl: '/purchase_order/{id}/print',
        exportUrl: '/purchase_order/export',
        importUrl: '/purchase_order/import',
        templateUrl: '/export/template/purchase_order'
    },
    transfer: {
        match: /^\/transfer(\/?$|\/add|\/\d+)/,
        navigator: true,
        detailUrl: '/transfer/{id}',
        addUrl: '/transfer/add',
        listUrl: '/transfer',
        tableId: 'transferTable',
        deleteUrl: '/transfer/batch_delete',
        detailDeleteUrl: '/transfer/{id}/delete',
        detailPrintUrl: '/transfer/{id}/print',
        detailExportUrl: '/transfer/{id}/export',
        exportUrl: '/transfer/export',
        importUrl: '/transfer/import',
        templateUrl: '/export/template/transfer'
    },
    adjustment: {
        match: /^\/adjustment(\/?$|\/add|\/\d+)/,
        navigator: true,
        detailUrl: '/adjustment/{id}',
        addUrl: '/adjustment/add',
        listUrl: '/adjustment',
        tableId: 'adjustmentTable',
        deleteUrl: '/adjustment/batch_delete',
        detailDeleteUrl: '/adjustment/{id}/delete',
        exportUrl: '/adjustment/export',
        importUrl: '/adjustment/import',
        templateUrl: '/export/template/adjustment'
    },
    check: {
        match: /^\/(?:check|inventory_check)(\/?$|\/add|\/\d+)/,
        navigator: true,
        detailUrl: '/check/{id}',
        addUrl: '/check/add',
        listUrl: '/check',
        tableId: 'checkTable',
        deleteUrl: '/check/batch_delete',
        detailDeleteUrl: '/check/{id}/delete',
        detailPrintUrl: '/check/{id}/print',
        detailExportUrl: '/check/{id}/export',
        exportUrl: '/check/export',
        importUrl: '/check/import',
        templateUrl: '/export/template/check',
        printListUrl: '/report/stock/print'
    },
    bom: {
        match: /^\/bom(\/?$|\/add|\/\d+)/,
        navigator: true,
        detailUrl: '/bom/{id}',
        addUrl: '/bom/add',
        listUrl: '/bom',
        tableId: 'bomTable',
        deleteUrl: '/bom/batch_delete',
        detailDeleteUrl: '/bom/{id}/delete',
        exportUrl: '/bom/export',
        importUrl: '/bom/import',
        templateUrl: '/export/template/bom'
    },
    requisition: {
        match: /^\/(?:requisition|production_requisition)(\/?$|\/add|\/\d+)/,
        navigator: true,
        detailUrl: '/requisition/{id}',
        addUrl: '/requisition/add',
        listUrl: '/requisition',
        tableId: 'requisitionTable',
        deleteUrl: '/requisition/batch_delete',
        detailDeleteUrl: '/requisition/{id}/delete',
        detailPrintUrl: '/requisition/{id}/print',
        detailExportUrl: '/requisition/{id}/export',
        exportUrl: '/requisition/export',
        importUrl: '/requisition/import',
        templateUrl: '/export/template/requisition'
    },
    subcontract: {
        match: /^\/subcontract(\/?$|\/\d+)/,
        navigator: true,
        detailUrl: '/subcontract/{id}',
        addTarget: '#addModal',
        listUrl: '/subcontract',
        deleteUrl: '/subcontract/batch_delete',
        detailDeleteUrl: '/subcontract/{id}/delete',
        exportUrl: '/subcontract/export',
        importUrl: '/subcontract/import',
        templateUrl: '/export/template/subcontract'
    },
    subcontract_issue: {
        match: /^\/(?:subcontract_issue|subcontract\/issue)(\/?$|\/\d+)/,
        navigator: true,
        detailUrl: '/subcontract_issue/{id}',
        addTarget: '#addModal',
        listUrl: '/subcontract_issue',
        deleteUrl: '/subcontract_issue/batch_delete',
        detailDeleteUrl: '/subcontract/issue/delete/{id}',
        exportUrl: '/subcontract_issue/export',
        importUrl: '/subcontract_issue/import',
        templateUrl: '/export/template/subcontract_issue'
    },
    subcontract_receive: {
        match: /^\/(?:subcontract_receive|subcontract\/receive)(\/?$|\/\d+)/,
        navigator: true,
        detailUrl: '/subcontract_receive/{id}',
        addTarget: '#addModal',
        listUrl: '/subcontract_receive',
        deleteUrl: '/subcontract_receive/batch_delete',
        detailDeleteUrl: '/subcontract/receive/delete/{id}',
        exportUrl: '/subcontract_receive/export',
        importUrl: '/subcontract_receive/import',
        templateUrl: '/export/template/subcontract_receive'
    },
    material: { match: /^\/material(\/?$|\/add)/, addTarget: '#addModal', listUrl: '/material', tableId: 'materialTable', deleteUrl: '/material/delete', exportUrl: '/material/export', importUrl: '/material/import', templateUrl: '/material/download_template' },
    category: { match: /^\/category\/?$/, addTarget: '#addModal', listUrl: '/category', tableId: 'categoryTable', deleteUrl: '/category/delete', exportUrl: '/category/export', importUrl: '/category/import', templateUrl: '/category/download_template' },
    unit: { match: /^\/unit\/?$/, addTarget: '#addModal', listUrl: '/unit', tableId: 'unitTable', deleteUrl: '/unit/delete', exportUrl: '/unit/export', importUrl: '/unit/import', templateUrl: '/unit/download_template' },
    supplier: { match: /^\/supplier\/?$/, addTarget: '#addModal', listUrl: '/supplier', tableId: 'supplierTable', deleteUrl: '/supplier/delete', exportUrl: '/supplier/export', importUrl: '/supplier/import', templateUrl: '/supplier/download_template' },
    customer: { match: /^\/customer\/?$/, addTarget: '#addModal', listUrl: '/customer', tableId: 'customerTable', deleteUrl: '/customer/delete', exportUrl: '/customer/export', importUrl: '/customer/import', templateUrl: '/customer/download_template' },
    warehouse: { match: /^\/warehouse\/?$/, addTarget: '#addModal', listUrl: '/warehouse', tableId: 'warehouseTable', deleteUrl: '/warehouse/delete', exportUrl: '/warehouse/export', importUrl: '/warehouse/import', templateUrl: '/warehouse/download_template' },
    department: { match: /^\/department\/?$/, addTarget: '#addModal', listUrl: '/department', tableId: 'departmentTable', deleteUrl: '/department/delete', exportUrl: '/department/export', importUrl: '/department/import', templateUrl: '/department/download_template' },
    employee: { match: /^\/employee\/?$/, addTarget: '#addModal', listUrl: '/employee', tableId: 'employeeTable', deleteUrl: '/employee/delete', exportUrl: '/employee/export', importUrl: '/employee/import', templateUrl: '/employee/download_template' },
    sales: {
        match: /^\/sales(\/?$|\/add|\/\d+(?:\/edit)?|\/outbound_selection|\/outbound)/,
        navigator: true,
        detailUrl: '/sales/{id}',
        addUrl: '/sales/add',
        listUrl: '/sales',
        tableId: 'salesOrderTable',
        deleteUrl: '/sales/batch_delete',
        detailDeleteUrl: '/sales/{id}/delete',
        detailPrintUrl: '/sales/{id}/print',
        exportUrl: '/sales/export',
        importUrl: '/sales/import',
        templateUrl: '/sales/download_template'
    }
};

function getWmsActionModule() {
    var path = window.location.pathname;
    for (var key in WMS_ACTION_MODULES) {
        if (WMS_ACTION_MODULES[key].match.test(path)) {
            return Object.assign({ key: key }, WMS_ACTION_MODULES[key]);
        }
    }
    return null;
}

function getCurrentRecordId() {
    var match = window.location.pathname.match(/\/(\d+)(?:\/(?:edit|detail))?\/?$/);
    return match ? match[1] : null;
}

function isFormPage() {
    return /\/add(?:\/)?$/.test(window.location.pathname) ||
        !!document.querySelector('#addForm, #docForm') ||
        !!document.querySelector('[name="order_id"]');
}

function openUrl(url, target) {
    if (!url) return false;
    if (target === '_blank') window.open(url, '_blank');
    else window.location.href = url;
    return true;
}

function buildModuleUrl(pattern, id) {
    return pattern && id ? pattern.replace('{id}', encodeURIComponent(id)) : '';
}

function buildCurrentFilteredUrl(baseUrl) {
    if (!baseUrl) return '';
    var url = new URL(baseUrl, window.location.origin);
    var currentParams = new URLSearchParams(window.location.search);
    var ignoredParams = new Set(['page', 'embedded']);
    currentParams.forEach(function(value, key) {
        if (ignoredParams.has(key) || value === '') return;
        url.searchParams.set(key, value);
    });
    return url.pathname + url.search;
}

function preserveEmbeddedUrl(url) {
    var isEmbedded = document.body.classList.contains('embedded-page') ||
        new URLSearchParams(window.location.search).get('embedded') === '1';
    return isEmbedded ? withEmbeddedParam(url) : url;
}

function escapeHtml(value) {
    var map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    };
    return String(value == null ? '' : value).replace(/[&<>"']/g, function(ch) {
        return map[ch];
    });
}

function openAdd(module) {
    if (module.addTarget) {
        var target = document.querySelector(module.addTarget);
        if (target && window.bootstrap) new bootstrap.Modal(target).show();
        return;
    }
    if (module.key === 'in_order') {
        var businessType = new URLSearchParams(window.location.search).get('business_type') || '';
        if (businessType === '产品入库') {
            openUrl('/in_order/add?type=product');
            return;
        }
    }
    openUrl(module.addUrl || module.listUrl);
}

function saveCurrentPage() {
    if (typeof window.submitForm === 'function') {
        try {
            if (window.submitForm.length >= 1) window.submitForm(false);
            else window.submitForm();
            return true;
        } catch (e) {
            showToast('保存失败：' + e.message, 'danger', 3600);
            return true;
        }
    }
    if (typeof window.submitAdd === 'function') {
        window.submitAdd();
        return true;
    }
    var saveBtn = document.getElementById('saveBtn');
    if (saveBtn) {
        saveBtn.click();
        return true;
    }
    var form = document.querySelector('#addForm, #docForm, form');
    if (form) {
        if (form.requestSubmit) form.requestSubmit();
        else form.submit();
        return true;
    }
    showToast('当前页面没有可保存的表单', 'warning');
    return false;
}

function getSelectedIds(module) {
    var tableId = module.tableId;
    if (!tableId) {
        var table = document.querySelector('table[id]');
        tableId = table ? table.id : '';
    }
    var selector = '.check-item:checked, .itemCheck:checked, .order-check:checked';
    var scope = tableId ? document.getElementById(tableId) : document;
    if (!scope) scope = document;
    return Array.from(scope.querySelectorAll(selector))
        .map(function(item) { return item.value; })
        .filter(Boolean);
}

function postJsonForAction(url, body) {
    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {})
    }).then(function(r) { return r.json(); });
}

function postDetailDeletes(module, ids) {
    return Promise.all(ids.map(function(id) {
        return fetch(buildModuleUrl(module.detailDeleteUrl, id), { method: 'POST' })
            .then(function(r) { return r.json(); })
            .catch(function(err) { return { status: 'error', msg: err.message }; });
    })).then(function(results) {
        var success = results.filter(function(item) { return item.status === 'success'; }).length;
        var failed = results.filter(function(item) { return item.status !== 'success'; });
        if (failed.length) {
            return {
                status: success ? 'partial' : 'error',
                msg: success + ' 条删除成功，' + failed.length + ' 条失败：' + (failed[0].msg || '删除失败')
            };
        }
        return { status: 'success', msg: '删除成功，共删除 ' + success + ' 条记录' };
    });
}

async function deleteCurrent(module) {
    if (!module.deleteUrl && !module.detailDeleteUrl) {
        showToast('当前页面暂未配置删除接口', 'warning');
        return;
    }
    var ids = getSelectedIds(module);
    if (!ids.length) {
        var recordId = getCurrentRecordId();
        if (recordId) ids = [recordId];
    }
    if (!ids.length) {
        showToast('请选择要删除的记录', 'warning');
        return;
    }
    var confirmed = await showConfirm('确定删除选中的 ' + ids.length + ' 条记录吗？', { title: '删除确认' });
    if (!confirmed) return;
    var deleteRequest = module.deleteUrl
        ? postJsonForAction(module.deleteUrl, { ids: ids })
        : postDetailDeletes(module, ids);
    deleteRequest
    .then(function(res) {
        if (res.status === 'success' || res.status === 'partial') {
            showToast(res.msg || '删除成功', 'success');
            setTimeout(function() { window.location.href = module.listUrl || window.location.pathname; }, 650);
        } else {
            showToast(res.msg || '删除失败', 'danger', 3600);
        }
    })
    .catch(function(err) { showToast('删除失败：' + err.message, 'danger', 3600); });
}

function printCurrent(module) {
    var id = getCurrentRecordId();
    if (id && module.detailPrintUrl) {
        window.open(buildModuleUrl(module.detailPrintUrl, id), '_blank');
        return;
    }
    if (module.printListUrl) {
        window.open(module.printListUrl, '_blank');
        return;
    }
    window.print();
}

function getModuleFilename(module, suffix) {
    var title = document.title || module.key || 'wms';
    return title.replace(/[\\/:*?"<>|]+/g, '_').replace(/\s+/g, '_') + '_' + suffix;
}

function downloadBlob(content, filename, mime) {
    var blob = new Blob([content], { type: mime || 'text/plain;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
}

function csvEscape(value) {
    value = value == null ? '' : String(value).replace(/\r?\n/g, ' ');
    return /[",\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
}

function exportVisibleTable(module) {
    var table = document.querySelector('table');
    if (!table) {
        showToast('当前页面没有可导出的表格', 'warning');
        return;
    }
    var rows = Array.from(table.querySelectorAll('tr')).map(function(row) {
        return Array.from(row.cells).map(function(cell) {
            return csvEscape(cell.innerText.trim());
        }).join(',');
    }).join('\r\n');
    downloadBlob('\ufeff' + rows, getModuleFilename(module, '导出.csv'), 'text/csv;charset=utf-8');
}

function downloadFallbackTemplate(module) {
    var templateColumns = {
        transfer: ['单据编号', '日期', '调出仓库', '调入仓库', '物料编码', '物料名称', '规格', '单位', '数量', '备注'],
        adjustment: ['单据编号', '日期', '调整类型', '物料编码', '物料名称', '规格', '单位', '数量', '库位', '原因', '备注'],
        check: ['单据编号', '日期', '物料编码', '物料名称', '规格', '单位', '系统库存', '实际库存', '差异原因', '备注'],
        requisition: ['单据编号', '日期', '工单', '用途', 'BOM编号', '物料编码', '物料名称', '规格', '单位', '数量', '备注'],
        purchase_request: ['申请编号', '日期', '申请人', '部门', '紧急程度', '期望到货', '物料编码', '物料名称', '规格', '单位', '数量', '预估单价', '推荐供应商', '备注'],
        after_sale_out: ['单据编号', '日期', '客户', '联系人', '电话', '售后原因', '物料编码', '物料名称', '规格', '单位', '数量', '单价', '备注'],
        subcontract: ['单据编号', '日期', '加工厂商', '联系人', '电话', '交货期限', '物料编码', '物料名称', '规格', '单位', '数量', '备注'],
        subcontract_issue: ['发料单号', '日期', '委外加工单号', '加工厂商', '物料编码', '物料名称', '规格', '单位', '数量', '备注'],
        subcontract_receive: ['入库单号', '日期', '委外加工单号', '加工厂商', '物料编码', '物料名称', '规格', '单位', '收货数量', '报废数量', '单价', '备注']
    };
    var columns = templateColumns[module.key] || ['单据编号', '日期', '物料编码', '物料名称', '规格', '单位', '数量', '备注'];
    var csv = '\ufeff' + columns.map(csvEscape).join(',') + '\r\n';
    downloadBlob(csv, getModuleFilename(module, '导入导出模板.csv'), 'text/csv;charset=utf-8');
}

function showImportModalForModule(module) {
    if (!module.importUrl) {
        showToast('当前模块暂未配置导入接口', 'warning');
        return;
    }
    var old = document.getElementById('cbGlobalImportModal');
    if (old) old.remove();
    var html = '' +
        '<div class="modal fade" id="cbGlobalImportModal" tabindex="-1">' +
        '<div class="modal-dialog"><div class="modal-content">' +
        '<div class="modal-header"><h5 class="modal-title"><i class="bi bi-upload"></i> 导入</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>' +
        '<div class="modal-body"><input type="file" class="form-control" id="cbGlobalImportFile" accept=".xlsx,.xls"><div class="form-text mt-2">建议先下载导入模板，按模板格式填写后导入。</div></div>' +
        '<div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button><button type="button" class="btn btn-primary" id="cbGlobalImportSubmit">导入</button></div>' +
        '</div></div></div>';
    document.body.insertAdjacentHTML('beforeend', html);
    var modalEl = document.getElementById('cbGlobalImportModal');
    var modal = new bootstrap.Modal(modalEl);
    document.getElementById('cbGlobalImportSubmit').addEventListener('click', function() {
        var fileInput = document.getElementById('cbGlobalImportFile');
        if (!fileInput.files.length) {
            showToast('请选择导入文件', 'warning');
            return;
        }
        var formData = new FormData();
        formData.append('file', fileInput.files[0]);
        fetch(module.importUrl, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: formData
        })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === 'success') {
                showToast(res.msg || '导入成功', 'success');
                modal.hide();
                setTimeout(function() { location.reload(); }, 800);
            } else {
                showToast(res.msg || '导入失败', 'danger', 4200);
            }
        })
        .catch(function(err) { showToast('导入失败：' + err.message, 'danger', 4200); });
    });
    modal.show();
}

function openSettings(module) {
    if (module.printTemplateUrl) {
        window.open(module.printTemplateUrl, '_blank');
        return;
    }
    var btn = document.querySelector('.cb-column-toggle-btn, [onclick*="Column"], [onclick*="Setting"], [onclick*="setting"]');
    if (btn) {
        btn.click();
        return;
    }
    showToast('可以拖拽表头、调整列宽，设置会自动保存', 'info', 3200);
}

function exportCurrent(module) {
    var id = getCurrentRecordId();
    if (id && module.detailExportUrl) {
        window.open(buildModuleUrl(module.detailExportUrl, id), '_blank');
        return;
    }
    if (!openUrl(buildCurrentFilteredUrl(module.exportUrl), '_blank')) exportVisibleTable(module);
}

function openTemplate(module) {
    if (!openUrl(module.templateUrl, '_blank')) downloadFallbackTemplate(module);
}

function normalizeShareText(value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
}

function getShareCellText(cell) {
    if (!cell) return '';
    var clone = cell.cloneNode(true);
    clone.querySelectorAll('button, input, select, textarea, .resize-handle, .col-resize, script, style, i, svg').forEach(function(node) {
        node.remove();
    });
    return normalizeShareText(clone.innerText || clone.textContent || '');
}

function isShareColumn(label) {
    label = normalizeShareText(label);
    if (!label) return false;
    return !/^(操作|标签|选择)$/.test(label);
}

function isVisibleTableCell(cell) {
    if (!cell) return false;
    return window.getComputedStyle(cell).display !== 'none';
}

function buildDocumentShareText(module) {
    var parts = [];
    var title = normalizeShareText(
        (document.querySelector('.order-title') || document.querySelector('h1, h2, .page-title'))?.textContent
    ) || document.title || '单据';
    parts.push(title);

    var infoItems = Array.from(document.querySelectorAll('.order-info-card .info-item')).map(function(item) {
        var label = normalizeShareText(item.querySelector('.info-label')?.textContent);
        var value = normalizeShareText(item.querySelector('.info-value')?.textContent);
        return label && value ? label + '：' + value : '';
    }).filter(Boolean);

    if (infoItems.length) {
        parts.push('', '单据信息');
        infoItems.forEach(function(line) { parts.push(line); });
    }

    var table = document.querySelector('#itemTable') || document.querySelector('.order-table-container table');
    if (table) {
        var sectionTitle = normalizeShareText(document.querySelector('.order-table-container .table-header-custom')?.textContent) || '单据明细';
        var headerCells = Array.from(table.querySelectorAll('thead th'));
        var includedIndexes = [];
        var headers = [];

        headerCells.forEach(function(th, index) {
            var label = getShareCellText(th);
            if (isVisibleTableCell(th) && isShareColumn(label)) {
                includedIndexes.push(index);
                headers.push(label);
            }
        });

        var detailLines = [];
        Array.from(table.querySelectorAll('tbody tr')).forEach(function(row) {
            if (row.querySelector('.empty-state')) return;
            var values = includedIndexes.map(function(index) {
                return getShareCellText(row.cells[index]) || '-';
            });
            if (values.some(function(value) { return value && value !== '-'; })) {
                detailLines.push(values.join(' | '));
            }
        });

        if (headers.length && detailLines.length) {
            parts.push('', sectionTitle);
            parts.push(headers.join(' | '));
            detailLines.forEach(function(line) { parts.push(line); });
        }

        var totalLines = Array.from(table.querySelectorAll('tfoot tr')).map(function(row) {
            return Array.from(row.cells).map(getShareCellText).filter(Boolean).join(' | ');
        }).filter(Boolean);
        if (totalLines.length) {
            parts.push('', '合计');
            totalLines.forEach(function(line) { parts.push(line); });
        }
    }

    var text = parts.join('\n').replace(/\n{3,}/g, '\n\n').trim();
    var hasDocumentContent = infoItems.length || table;
    return hasDocumentContent ? text : '';
}

function filenameFromDisposition(disposition, fallback) {
    var filename = fallback || '单据.pdf';
    if (!disposition) return filename;
    var utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match && utf8Match[1]) {
        try {
            return decodeURIComponent(utf8Match[1].replace(/["']/g, ''));
        } catch (error) {}
    }
    var match = disposition.match(/filename="?([^";]+)"?/i);
    return match && match[1] ? match[1] : filename;
}

function shareImageFile(blob, filename, title) {
    var file = new File([blob], filename, { type: 'image/png' });
    if (navigator.clipboard && window.ClipboardItem) {
        return navigator.clipboard.write([
            new ClipboardItem({ 'image/png': blob })
        ]).then(function() {
            showToast('单据图片已复制，打开微信聊天框粘贴即可发送', 'success', 4200);
        }).catch(function() {
            downloadBlob(blob, filename, 'image/png');
            showToast('图片复制失败，已下载单据图片', 'warning', 3200);
        });
    }
    downloadBlob(blob, filename, 'image/png');
    showToast('单据图片已生成并下载', 'success', 2600);
    return Promise.resolve();
}

function smartShare(module) {
    if (window.__smartShareBusy) return;
    var id = getCurrentRecordId();
    if (!id || !module || !module.key) {
        showToast('请先打开一张具体单据再分享', 'warning');
        return;
    }
    window.__smartShareBusy = true;
    var title = normalizeShareText(
        (document.querySelector('.order-title') || document.querySelector('h1, h2, .page-title'))?.textContent
    ) || document.title || '单据';
    var url = '/api/share_image/' + encodeURIComponent(module.key) + '/' + encodeURIComponent(id);
    showToast('正在生成单据图片...', 'info', 1800);
    fetch(url, { headers: { 'Accept': 'image/png' } })
        .then(function(response) {
            if (!response.ok) {
                return response.json().catch(function() { return {}; }).then(function(data) {
                    throw new Error(data.msg || '单据图片生成失败');
                });
            }
            var filename = filenameFromDisposition(response.headers.get('Content-Disposition'), title.replace(/[\\/:*?"<>|]+/g, '_') + '.png');
            return response.blob().then(function(blob) {
                return shareImageFile(blob, filename, title);
            });
        })
        .catch(function(error) {
            showToast(error.message || '单据图片分享失败', 'danger', 4200);
        })
        .finally(function() {
            window.__smartShareBusy = false;
        });
}

function getDocumentNavigationApiUrl(module, keyword) {
    var params = new URLSearchParams();
    var currentId = getCurrentRecordId();
    if (currentId) params.set('current_id', currentId);
    if (keyword) params.set('q', keyword);
    var query = params.toString();
    return '/api/document_navigation/' + encodeURIComponent(module.key) + (query ? '?' + query : '');
}

function fetchDocumentNavigation(module, keyword) {
    return fetch(getDocumentNavigationApiUrl(module, keyword), {
        headers: { 'Accept': 'application/json' }
    })
    .then(function(response) {
        if (!response.ok) throw new Error('单据导航查询失败');
        return response.json();
    })
    .then(function(data) {
        if (data.status !== 'success') throw new Error(data.msg || '单据导航查询失败');
        return data;
    });
}

function getDocumentDetailUrl(module, id, row) {
    if (row && row.url) return row.url;
    return buildModuleUrl(module.detailUrl, id) || ((module.listUrl || '') + '/' + encodeURIComponent(id));
}

function openDocumentById(module, id, row) {
    if (!id) {
        showToast('没有可打开的单据', 'warning');
        return;
    }
    openUrl(preserveEmbeddedUrl(getDocumentDetailUrl(module, id, row)));
}

function findDocumentRow(data, id) {
    id = String(id);
    return (data.list || []).find(function(row) {
        return String(row.id) === id;
    }) || null;
}

function navigateDocument(module, target) {
    fetchDocumentNavigation(module)
    .then(function(data) {
        var targetId = data[target + '_id'];
        if (!targetId && !getCurrentRecordId()) {
            if (target === 'prev') targetId = data.last_id;
            else if (target === 'next') targetId = data.first_id;
        }
        if (!targetId) {
            if ((target === 'prev' || target === 'next') && !getCurrentRecordId()) {
                showToast('暂无可导航的单据', 'warning');
            } else if (target === 'prev') {
                showToast('已经是首张单据', 'info');
            } else if (target === 'next') {
                showToast('已经是末张单据', 'info');
            } else {
                showToast('暂无可导航的单据', 'warning');
            }
            return;
        }
        openDocumentById(module, targetId, findDocumentRow(data, targetId));
    })
    .catch(function(error) {
        showToast(error.message || '单据导航失败', 'danger', 3600);
    });
}

function formatDocumentStatus(status) {
    var map = {
        pending: '未审核/待完成',
        completed: '已完成',
        approved: '已审核',
        rejected: '已驳回',
        processing: '处理中',
        cancelled: '已取消',
        active: '启用',
        inactive: '停用'
    };
    return map[status] || status || '';
}

function renderDocumentSearchResults(container, meta, data) {
    var rows = data.list || [];
    if (!rows.length) {
        meta.textContent = '未找到匹配单据';
        container.innerHTML = '<div class="cb-doc-search-empty"><i class="bi bi-search"></i><span>未找到匹配单据</span></div>';
        return;
    }
    meta.textContent = '共匹配 ' + (data.total || rows.length) + ' 张单据' + (data.total > rows.length ? '，显示前 ' + rows.length + ' 张' : '');
    container.innerHTML = rows.map(function(row) {
        var status = formatDocumentStatus(row.status);
        return '' +
            '<button type="button" class="cb-doc-search-row" data-id="' + escapeHtml(row.id) + '">' +
                '<span class="cb-doc-search-icon"><i class="bi bi-file-earmark-text"></i></span>' +
                '<span class="cb-doc-search-main">' +
                    '<span class="cb-doc-search-no">' + escapeHtml(row.no || ('#' + row.id)) + '</span>' +
                    '<span class="cb-doc-search-title">' + escapeHtml(row.title || '无标题') + '</span>' +
                '</span>' +
                '<span class="cb-doc-search-date">' + escapeHtml(row.date || '') + '</span>' +
                '<span class="cb-doc-search-status">' + escapeHtml(status) + '</span>' +
                '<span class="cb-doc-search-open"><i class="bi bi-arrow-right-short"></i></span>' +
            '</button>';
    }).join('');
}

function showDocumentSearchModal(module) {
    if (!window.bootstrap) {
        var keyword = prompt('请输入单号、客户、供应商、用途、物料编码、物料名称或规格');
        if (keyword === null) return;
        fetchDocumentNavigation(module, keyword).then(function(data) {
            if (!data.list.length) {
                showToast('未找到匹配单据', 'warning');
                return;
            }
            openDocumentById(module, data.list[0].id, data.list[0]);
        }).catch(function(error) {
            showToast(error.message || '查找单据失败', 'danger', 3600);
        });
        return;
    }

    var old = document.getElementById('cbDocumentSearchModal');
    if (old) old.remove();
    var html = '' +
        '<div class="modal fade cb-doc-search-modal" id="cbDocumentSearchModal" tabindex="-1">' +
        '<div class="modal-dialog modal-lg modal-dialog-scrollable"><div class="modal-content">' +
        '<div class="modal-header">' +
            '<h5 class="modal-title"><i class="bi bi-search-heart"></i> 查找单据</h5>' +
            '<button type="button" class="btn-close" data-bs-dismiss="modal"></button>' +
        '</div>' +
        '<div class="modal-body">' +
        '<div class="cb-doc-search-input-wrap">' +
                '<i class="bi bi-search"></i>' +
                '<input type="search" class="form-control" id="cbDocumentSearchInput" placeholder="输入单号、未审核/待完成、客户、供应商、物料编码、名称、规格" autocomplete="off">' +
            '</div>' +
            '<div class="cb-doc-search-meta" id="cbDocumentSearchMeta">正在加载单据...</div>' +
            '<div class="cb-doc-search-results" id="cbDocumentSearchResults"></div>' +
        '</div>' +
        '</div></div></div>';
    document.body.insertAdjacentHTML('beforeend', html);

    var modalEl = document.getElementById('cbDocumentSearchModal');
    var input = document.getElementById('cbDocumentSearchInput');
    var meta = document.getElementById('cbDocumentSearchMeta');
    var results = document.getElementById('cbDocumentSearchResults');
    var modal = new bootstrap.Modal(modalEl);
    var latestRows = [];
    var timer = null;

    function load(keyword) {
        meta.textContent = '正在加载单据...';
        fetchDocumentNavigation(module, keyword)
        .then(function(data) {
            latestRows = data.list || [];
            renderDocumentSearchResults(results, meta, data);
        })
        .catch(function(error) {
            latestRows = [];
            meta.textContent = error.message || '查找单据失败';
            results.innerHTML = '';
        });
    }

    input.addEventListener('input', function() {
        clearTimeout(timer);
        timer = setTimeout(function() {
            load(input.value.trim());
        }, 180);
    });

    results.addEventListener('click', function(event) {
        var rowEl = event.target.closest('.cb-doc-search-row');
        if (!rowEl) return;
        var row = latestRows.find(function(item) {
            return String(item.id) === String(rowEl.dataset.id);
        });
        if (row) {
            modal.hide();
            openDocumentById(module, row.id, row);
        }
    });

    modalEl.addEventListener('shown.bs.modal', function() {
        input.focus();
        input.select();
    });
    modal.show();
    load('');
}

function createDocumentNavigationGroup(module) {
    if (!module.navigator) return null;
    var group = document.createElement('div');
    group.className = 'cb-doc-nav';
    group.setAttribute('aria-label', '单据导航');

    var items = [
        { icon: 'bi-search-heart', label: '查找单据', title: '查找单据', action: function() { showDocumentSearchModal(module); } },
        { icon: 'bi-chevron-bar-left', label: '首张', title: '首张', action: function() { navigateDocument(module, 'first'); } },
        { icon: 'bi-chevron-left', label: '上一张', title: '上一张', action: function() { navigateDocument(module, 'prev'); } },
        { icon: 'bi-chevron-right', label: '下一张', title: '下一张', action: function() { navigateDocument(module, 'next'); } },
        { icon: 'bi-chevron-bar-right', label: '末张', title: '末张', action: function() { navigateDocument(module, 'last'); } }
    ];

    items.forEach(function(item) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-sm cb-doc-nav-btn';
        btn.title = item.title;
        btn.innerHTML = '<span class="cb-doc-nav-icon"><i class="bi ' + item.icon + '"></i></span><span class="cb-doc-nav-label">' + item.label + '</span>';
        btn.addEventListener('click', item.action);
        group.appendChild(btn);
    });
    return group;
}

// 单据明细表行操作菜单：增行、插行、复制行、删除行。
window.WmsDetailRowActions = (function() {
    var configs = [];
    var activeContext = null;
    var menu = null;
    var actions = [
        { key: 'add', label: '增行', shortcut: 'Alt+1' },
        { key: 'insert', label: '插行', shortcut: 'Alt+2' },
        { key: 'copy', label: '复制行', shortcut: 'Alt+3' },
        { key: 'remove', label: '删除行', shortcut: 'Alt+4' }
    ];

    function getMenu() {
        if (menu) return menu;
        menu = document.createElement('div');
        menu.className = 'wms-row-context-menu';
        menu.setAttribute('role', 'menu');
        menu.innerHTML = actions.map(function(action) {
            return '<button type="button" data-action="' + action.key + '">' +
                '<span>' + action.label + '</span>' +
                '<kbd>' + action.shortcut + '</kbd>' +
                '</button>';
        }).join('');
        menu.addEventListener('click', function(event) {
            var button = event.target.closest('button[data-action]');
            if (!button || button.disabled) return;
            runAction(button.dataset.action);
        });
        document.body.appendChild(menu);
        return menu;
    }

    function hideMenu() {
        if (menu) menu.classList.remove('show');
    }

    function isEditable(config) {
        if (typeof config.editable === 'function') return !!config.editable();
        return config.editable !== false;
    }

    function rowIsEmpty(row) {
        return !row || !!row.querySelector('.empty-state, td[colspan]');
    }

    function findConfigForElement(element) {
        for (var i = configs.length - 1; i >= 0; i--) {
            var config = configs[i];
            var table = document.querySelector(config.tableSelector);
            if (table && table.contains(element)) {
                config.table = table;
                return config;
            }
        }
        return null;
    }

    function findRow(config, element, allowEmpty) {
        var table = config.table || document.querySelector(config.tableSelector);
        if (!table || !element) return null;
        var row = element.closest(config.rowSelector || 'tbody tr');
        if (!row || !table.contains(row) || row.closest('thead,tfoot')) return null;
        if (!allowEmpty && rowIsEmpty(row)) return null;
        return row;
    }

    function setActive(config, row) {
        if (activeContext && activeContext.row) {
            activeContext.row.classList.remove('wms-row-action-active');
        }
        activeContext = { config: config, row: row || null };
        if (row) row.classList.add('wms-row-action-active');
        if (typeof config.onActiveRow === 'function') config.onActiveRow(row);
    }

    function actionEnabled(config, row, actionKey) {
        if (!isEditable(config)) return false;
        if (actionKey === 'add') return typeof config.add === 'function';
        if (!row || rowIsEmpty(row)) return false;
        if (actionKey === 'insert') return typeof config.insert === 'function';
        if (actionKey === 'copy') return typeof config.copy === 'function';
        if (actionKey === 'remove') return typeof config.remove === 'function';
        return false;
    }

    function showMenu(config, row, x, y) {
        if (!isEditable(config)) return;
        setActive(config, row);
        var menuEl = getMenu();
        actions.forEach(function(action) {
            var button = menuEl.querySelector('[data-action="' + action.key + '"]');
            if (button) button.disabled = !actionEnabled(config, row, action.key);
        });
        menuEl.style.left = x + 'px';
        menuEl.style.top = y + 'px';
        menuEl.classList.add('show');

        var rect = menuEl.getBoundingClientRect();
        var nextLeft = Math.min(x, window.innerWidth - rect.width - 8);
        var nextTop = Math.min(y, window.innerHeight - rect.height - 8);
        menuEl.style.left = Math.max(8, nextLeft) + 'px';
        menuEl.style.top = Math.max(8, nextTop) + 'px';
    }

    function rowFromFocus(config) {
        var table = config.table || document.querySelector(config.tableSelector);
        if (!table) return null;
        if (document.activeElement && table.contains(document.activeElement)) {
            return findRow(config, document.activeElement, false);
        }
        return activeContext && activeContext.config === config ? activeContext.row : null;
    }

    function currentContext() {
        if (activeContext && activeContext.config && document.querySelector(activeContext.config.tableSelector)) {
            activeContext.row = rowFromFocus(activeContext.config) || activeContext.row;
            return activeContext;
        }
        for (var i = configs.length - 1; i >= 0; i--) {
            var config = configs[i];
            var table = document.querySelector(config.tableSelector);
            if (table && document.activeElement && table.contains(document.activeElement)) {
                config.table = table;
                return { config: config, row: rowFromFocus(config) };
            }
        }
        return null;
    }

    function runAction(actionKey) {
        var context = currentContext();
        if (!context || !actionEnabled(context.config, context.row, actionKey)) {
            hideMenu();
            return;
        }
        hideMenu();
        if (actionKey === 'add') context.config.add(context.row);
        if (actionKey === 'insert') context.config.insert(context.row);
        if (actionKey === 'copy') context.config.copy(context.row);
        if (actionKey === 'remove') context.config.remove(context.row);
    }

    function register(config) {
        if (!config || !config.tableSelector) return;
        configs = configs.filter(function(item) {
            return item.tableSelector !== config.tableSelector;
        });
        configs.push(config);
        var table = document.querySelector(config.tableSelector);
        if (table) table.classList.add('wms-row-actions-table');
    }

    document.addEventListener('contextmenu', function(event) {
        var config = findConfigForElement(event.target);
        if (!config || !isEditable(config)) return;
        var row = findRow(config, event.target, true);
        if (!row) return;
        event.preventDefault();
        showMenu(config, rowIsEmpty(row) ? null : row, event.clientX, event.clientY);
    });

    document.addEventListener('click', function(event) {
        if (menu && !event.target.closest('.wms-row-context-menu')) hideMenu();
        var config = findConfigForElement(event.target);
        if (!config || !isEditable(config)) return;
        var row = findRow(config, event.target, false);
        if (row) setActive(config, row);
    });

    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            hideMenu();
            return;
        }
        if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        var keyMap = { '1': 'add', '2': 'insert', '3': 'copy', '4': 'remove' };
        var actionKey = keyMap[event.key];
        if (!actionKey) return;
        var context = currentContext();
        if (!context || !actionEnabled(context.config, context.row, actionKey)) return;
        event.preventDefault();
        runAction(actionKey);
    });

    window.addEventListener('scroll', hideMenu, true);
    window.addEventListener('resize', hideMenu);

    return {
        register: register,
        hide: hideMenu
    };
})();

function registerDetailRowActions(config) {
    if (window.WmsDetailRowActions) window.WmsDetailRowActions.register(config);
}

function initDocumentEntryMode() {
    var path = (window.location.pathname || '').replace(/\/+$/, '') || '/';
    var documentPathPatterns = [
        /^\/in_order\/add$/,
        /^\/in_order\/\d+(\/edit)?$/,
        /^\/sales\/add$/,
        /^\/sales\/\d+(\/edit)?$/,
        /^\/sales\/outbound_selection$/,
        /^\/out_order\/add$/,
        /^\/out_order\/\d+(\/edit)?$/,
        /^\/purchase_order\/add$/,
        /^\/purchase_order\/\d+(\/edit)?$/,
        /^\/purchase_request\/add$/,
        /^\/purchase_request\/\d+(\/edit)?$/,
        /^\/after_sale_out\/add$/,
        /^\/after_sale_out\/\d+(\/edit)?$/,
        /^\/adjustment\/add$/,
        /^\/adjustment\/\d+(\/edit)?$/,
        /^\/transfer\/add$/,
        /^\/transfer\/\d+(\/edit)?$/,
        /^\/check\/add$/,
        /^\/check\/\d+(\/edit)?$/,
        /^\/requisition\/add$/,
        /^\/requisition\/\d+(\/edit)?$/,
        /^\/bom\/add$/,
        /^\/bom\/\d+(\/edit)?$/
    ];
    var isDocumentPath = documentPathPatterns.some(function(pattern) {
        return pattern.test(path);
    });
    var tableSelectors = ['#docTable', '#adjustmentTable', '#materialTable', '#itemTable', '#bomItemsTable'];
    var tables = [];

    tableSelectors.forEach(function(selector) {
        document.querySelectorAll(selector).forEach(function(table) {
            if (tables.indexOf(table) !== -1) return;
            if (selector === '#materialTable' && !isDocumentPath) return;
            if (selector === '#itemTable' && !isDocumentPath && !table.closest('.modal')) return;
            if (selector === '#docTable' || selector === '#adjustmentTable' || selector === '#bomItemsTable' || isDocumentPath || table.closest('.modal')) {
                tables.push(table);
            }
        });
    });

    if (!tables.length) return;

    function closestWrapper(table) {
        return table.closest('.table-responsive, .doc-grid-wrapper, .adjust-grid-wrapper, .tplus-table-wrapper') || table.parentElement;
    }

    function ensureTabs(wrapper) {
        if (!wrapper || !wrapper.parentNode) return;
        var previous = wrapper.previousElementSibling;
        if (previous && previous.classList.contains('wms-doc-tabs')) return;

        var tabs = document.createElement('div');
        tabs.className = 'wms-doc-tabs';
        tabs.setAttribute('role', 'tablist');

        var detailTab = document.createElement('button');
        detailTab.type = 'button';
        detailTab.className = 'wms-doc-tab active';
        detailTab.setAttribute('role', 'tab');
        detailTab.setAttribute('aria-selected', 'true');
        detailTab.textContent = '\u660e\u7ec6';

        var summaryTab = document.createElement('button');
        summaryTab.type = 'button';
        summaryTab.className = 'wms-doc-tab';
        summaryTab.setAttribute('role', 'tab');
        summaryTab.setAttribute('aria-selected', 'false');
        summaryTab.disabled = true;
        summaryTab.textContent = '\u6c47\u603b';

        tabs.appendChild(detailTab);
        tabs.appendChild(summaryTab);
        wrapper.parentNode.insertBefore(tabs, wrapper);
    }

    function markToolbar(wrapper) {
        if (!wrapper) return;
        var current = wrapper.previousElementSibling;
        while (current && current.classList.contains('wms-doc-tabs')) {
            current = current.previousElementSibling;
        }
        if (current && current.querySelector && current.querySelector('.btn')) {
            current.classList.add('wms-entry-toolbar');
        }
    }

    var hasPageTable = tables.some(function(table) {
        return !table.closest('.modal');
    });
    if (hasPageTable || isDocumentPath) {
        document.body.classList.add('wms-doc-entry');
    }

    if (isDocumentPath) {
        document.querySelectorAll('.page-header, .doc-header, .adjust-header').forEach(function(header) {
            header.classList.add('wms-entry-header');
        });
        document.querySelectorAll('.card, .doc-page, .adjust-page').forEach(function(shell) {
            if (shell.querySelector('#materialTable, #docTable, #adjustmentTable, #itemTable')) {
                shell.classList.add('wms-entry-shell');
            }
        });
        document.querySelectorAll('.tplus-toolbar, .doc-toolbar, .adjust-toolbar').forEach(function(toolbar) {
            toolbar.classList.add('wms-entry-toolbar');
        });
    }

    tables.forEach(function(table) {
        var wrapper = closestWrapper(table);
        var modal = table.closest('.modal');
        table.classList.add('wms-entry-grid');
        if (wrapper) wrapper.classList.add('wms-entry-grid-wrapper');
        if (modal) modal.classList.add('wms-doc-entry-modal');
        var form = table.closest('form');
        if (form) form.classList.add('wms-entry-form');
        markToolbar(wrapper);
        ensureTabs(wrapper);
    });
}

function initMobileTableMode() {
    if (!isMobileViewport()) return;
    document.body.classList.add('wms-mobile');

    document.querySelectorAll('table').forEach(function(table) {
        var businessTableIds = ['docTable', 'adjustmentTable', 'materialTable', 'itemTable', 'bomItemsTable'];
        if (!table.classList.contains('table') && businessTableIds.indexOf(table.id) === -1) return;
        if (table.closest('.wms-mobile-card-list')) return;
        var wrapper = table.closest('.table-responsive, .table-responsive-wrapper, .wms-entry-grid-wrapper, .doc-grid-wrapper, .adjust-grid-wrapper, .tplus-table-wrapper');
        if (!wrapper) {
            wrapper = document.createElement('div');
            wrapper.className = 'table-responsive';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        }
        wrapper.classList.add('wms-mobile-table-scroll');
        table.classList.add('wms-mobile-table');
    });
}

function textFromCell(cell) {
    if (!cell) return '';
    var input = cell.querySelector('input, select, textarea');
    if (input) {
        if (input.tagName === 'SELECT') {
            return input.options[input.selectedIndex] ? input.options[input.selectedIndex].text.trim() : '';
        }
        return String(input.value || '').trim();
    }
    return String(cell.textContent || '').replace(/\s+/g, ' ').trim();
}

function headerLabelsForTable(table) {
    return Array.from(table.querySelectorAll('thead th')).map(function(th) {
        return String(th.textContent || '').replace(/\s+/g, ' ').trim();
    });
}

function shouldSkipMobileField(label, value) {
    if (!label && !value) return true;
    if (/^(选择|勾选|序号|行号|#)$/i.test(label)) return true;
    if (!value && /^(操作|动作)$/i.test(label)) return true;
    return false;
}

function initMobileListCards() {
    if (!isMobileViewport()) return;
    document.querySelectorAll('table.wms-mobile-table').forEach(function(table) {
        if (table.classList.contains('wms-entry-grid')) return;
        if (table.dataset.mobileCardsReady === 'true') return;
        var tbody = table.querySelector('tbody');
        if (!tbody) return;
        var rows = Array.from(tbody.querySelectorAll('tr')).filter(function(row) {
            return !row.querySelector('td[colspan]');
        });
        if (!rows.length) return;

        var labels = headerLabelsForTable(table);
        var cards = document.createElement('div');
        cards.className = 'wms-mobile-card-list';

        rows.forEach(function(row) {
            var cells = Array.from(row.children).filter(function(cell) { return cell.tagName === 'TD' || cell.tagName === 'TH'; });
            var card = document.createElement('article');
            card.className = 'wms-mobile-list-card';

            var titleCell = cells.find(function(cell, index) {
                var label = labels[index] || '';
                return cell.querySelector('a[href]') || /单号|编码|名称|客户|供应商|物料/.test(label);
            }) || cells[1] || cells[0];
            var titleText = textFromCell(titleCell) || '记录';
            var titleLink = titleCell ? titleCell.querySelector('a[href]') : null;

            var header = document.createElement('div');
            header.className = 'wms-mobile-list-card-header';
            if (titleLink) {
                var link = titleLink.cloneNode(true);
                link.className = 'wms-mobile-list-card-title';
                header.appendChild(link);
            } else {
                var title = document.createElement('div');
                title.className = 'wms-mobile-list-card-title';
                title.textContent = titleText;
                header.appendChild(title);
            }

            var statusCell = cells.find(function(cell, index) {
                return cell.querySelector('.badge') || /状态|执行/.test(labels[index] || '');
            });
            if (statusCell) {
                var status = document.createElement('div');
                status.className = 'wms-mobile-list-card-status';
                // XSS 防护：使用 cloneNode(true) 复制子节点而非重新解析 innerHTML，
                // 避免对原始 HTML 字符串再次执行解析（保留服务端 Jinja 转义结果，不重新评估脚本）
                Array.from(statusCell.childNodes).forEach(function(node) {
                    status.appendChild(node.cloneNode(true));
                });
                header.appendChild(status);
            }
            card.appendChild(header);

            var body = document.createElement('div');
            body.className = 'wms-mobile-list-card-body';
            cells.forEach(function(cell, index) {
                var label = labels[index] || '';
                var value = textFromCell(cell);
                if (cell === titleCell || cell === statusCell || shouldSkipMobileField(label, value)) return;
                if (/^(操作|动作)$/i.test(label)) return;
                var item = document.createElement('div');
                item.className = 'wms-mobile-field';
                item.innerHTML = '<span class="wms-mobile-field-label"></span><span class="wms-mobile-field-value"></span>';
                item.querySelector('.wms-mobile-field-label').textContent = label || '字段';
                item.querySelector('.wms-mobile-field-value').textContent = value || '-';
                body.appendChild(item);
            });
            card.appendChild(body);

            var actionCell = cells.find(function(cell, index) {
                return /^(操作|动作)$/i.test(labels[index] || '') || cell.querySelector('.btn, button, a[href]');
            });
            if (actionCell) {
                var actions = document.createElement('div');
                actions.className = 'wms-mobile-list-card-actions';
                Array.from(actionCell.querySelectorAll('a[href], button')).forEach(function(action) {
                    actions.appendChild(action.cloneNode(true));
                });
                if (actions.children.length) card.appendChild(actions);
            }

            cards.appendChild(card);
        });

        var wrapper = table.closest('.wms-mobile-table-scroll, .table-responsive, .table-responsive-wrapper');
        if (wrapper) {
            wrapper.classList.add('wms-mobile-list-source-hidden');
            wrapper.insertAdjacentElement('afterend', cards);
        }
        table.dataset.mobileCardsReady = 'true';
    });
}

function inputLabelFromCell(cell, index) {
    var table = cell.closest('table');
    var labels = table ? headerLabelsForTable(table) : [];
    return labels[index] || '';
}

function cloneCellControlsForMobile(row, card) {
    var cells = Array.from(row.children).filter(function(cell) { return cell.tagName === 'TD' || cell.tagName === 'TH'; });
    var title = document.createElement('div');
    title.className = 'wms-mobile-line-title';
    var rowNo = textFromCell(cells[0]) || String(Array.from(row.parentNode.children).indexOf(row) + 1);
    // XSS 防护：rowNo 来自表格单元格文本，转义后再插入 innerHTML
    title.innerHTML = '<span>明细 ' + escapeHtml(rowNo) + '</span><button type="button" class="wms-mobile-line-toggle" aria-expanded="true">收起</button>';
    card.appendChild(title);

    var fields = document.createElement('div');
    fields.className = 'wms-mobile-line-fields';
    cells.forEach(function(cell, index) {
        var label = inputLabelFromCell(cell, index);
        if (shouldSkipMobileField(label, textFromCell(cell))) return;
        var controls = Array.from(cell.querySelectorAll('input, select, textarea, button'));
        if (!controls.length && /^(操作|动作)$/.test(label)) controls = Array.from(cell.querySelectorAll('a, button'));
        if (!controls.length && !textFromCell(cell)) return;

        var field = document.createElement('div');
        field.className = /^(操作|动作)$/.test(label) ? 'wms-mobile-line-actions' : 'wms-mobile-line-field';
        var fieldLabel = document.createElement('label');
        fieldLabel.className = 'wms-mobile-line-label';
        fieldLabel.textContent = label || '字段';
        field.appendChild(fieldLabel);

        var controlWrap = document.createElement('div');
        controlWrap.className = 'wms-mobile-line-control';
        if (controls.length) {
            controls.forEach(function(control) {
                if (control.type === 'hidden') return;
                controlWrap.appendChild(control);
            });
        } else {
            controlWrap.textContent = textFromCell(cell) || '-';
        }
        field.appendChild(controlWrap);
        fields.appendChild(field);
    });
    card.appendChild(fields);

    title.querySelector('.wms-mobile-line-toggle').addEventListener('click', function() {
        var collapsed = card.classList.toggle('collapsed');
        this.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        this.textContent = collapsed ? '展开' : '收起';
    });
}

function initMobileDocumentCards() {
    if (!isMobileViewport()) return;
    document.querySelectorAll('table.wms-entry-grid').forEach(function(table) {
        if (table.dataset.mobileLineCardsReady === 'true') return;
        var tbody = table.querySelector('tbody');
        if (!tbody) return;
        var wrapper = table.closest('.wms-entry-grid-wrapper, .tplus-table-wrapper, .table-responsive');
        if (!wrapper) return;

        var labels = headerLabelsForTable(table);
        Array.from(tbody.querySelectorAll('tr')).forEach(function(row) {
            if (row.querySelector('td[colspan]')) return;
            Array.from(row.children).forEach(function(cell, index) {
                if (cell.tagName !== 'TD' && cell.tagName !== 'TH') return;
                var label = labels[index] || '';
                cell.dataset.mobileLabel = label;
            });
        });

        table.classList.add('wms-mobile-card-table');
        wrapper.classList.add('wms-mobile-document-card-wrapper');
        table.dataset.mobileLineCardsReady = 'true';
    });
}

function initTrueMobileMode() {
    if (!isMobileViewport()) return;
    initMobileListCards();
    initMobileDocumentCards();
}

function insertGlobalActionBar() {
    if (document.getElementById('cbGlobalActionBar')) return;
    var module = getWmsActionModule();
    if (!module) return;
    var content = document.querySelector('.embedded-content');
    if (!content) return;
    var bar = document.createElement('div');
    bar.className = 'cb-actionbar no-print';
    bar.id = 'cbGlobalActionBar';
    document.body.classList.add('cb-has-actionbar');
    if (isFormPage()) document.body.classList.add('cb-form-actionbar');
    var buttons = [
        { key: 'add', icon: 'bi-plus-lg', label: '新增', action: function() { openAdd(module); } },
        { key: 'save', icon: 'bi-save', label: '保存', action: saveCurrentPage },
        { key: 'delete', icon: 'bi-trash', label: '删除', action: function() { deleteCurrent(module); } },
        { divider: true },
        { key: 'settings', icon: 'bi-gear', label: '设置', action: function() { openSettings(module); } },
        { key: 'print', icon: 'bi-printer', label: '打印', action: function() { printCurrent(module); } },
        { divider: true },
        { key: 'import', icon: 'bi-upload', label: '导入', action: function() { showImportModalForModule(module); } },
        { key: 'export', icon: 'bi-download', label: '导出', action: function() { exportCurrent(module); } },
        { key: 'template', icon: 'bi-file-earmark-spreadsheet', label: '导入导出模板', action: function() { openTemplate(module); } },
        { divider: true },
        { key: 'share', icon: 'bi-share', label: '智能分享', action: function() { smartShare(module); } }
    ];
    buttons.forEach(function(item) {
        if (item.divider) {
            var divider = document.createElement('span');
            divider.className = 'cb-actionbar-divider';
            bar.appendChild(divider);
            return;
        }
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-sm';
        btn.innerHTML = '<i class="bi ' + item.icon + '"></i>' + item.label;
        btn.addEventListener('click', item.action);
        if (item.key === 'save' && !isFormPage()) btn.classList.add('disabled');
        if (item.key === 'delete' && !module.deleteUrl && !module.detailDeleteUrl) btn.classList.add('disabled');
        bar.appendChild(btn);
    });
    var navGroup = createDocumentNavigationGroup(module);
    if (navGroup) {
        var spacer = document.createElement('span');
        spacer.className = 'cb-actionbar-spacer';
        bar.appendChild(spacer);
        bar.appendChild(navGroup);
    }
    content.insertBefore(bar, content.firstChild);
}

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    if (document.body.classList.contains('embedded-page')) {
        document.addEventListener('click', function(event) {
            if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            const link = event.target.closest && event.target.closest('a[href]');
            if (!link || link.target === '_blank' || link.hasAttribute('download')) return;
            const rawHref = link.getAttribute('href');
            if (!rawHref || rawHref[0] === '#' || rawHref.startsWith('javascript:')) return;
            let target;
            try { target = new URL(rawHref, window.location.href); } catch (error) { return; }
            if (target.origin !== window.location.origin) return;
            target.searchParams.set('embedded', '1');
            link.href = target.pathname + target.search + target.hash;
        }, true);
    }

    // 确认框事件绑定
    document.getElementById('cbConfirmOk')?.addEventListener('click', function() {
        resolveConfirm(true);
    });
    document.getElementById('cbConfirmCancel')?.addEventListener('click', function() {
        resolveConfirm(false);
    });
    document.getElementById('cbConfirmOverlay')?.addEventListener('click', function(event) {
        if (event.target.id === 'cbConfirmOverlay') {
            resolveConfirm(false);
        }
    });

    // 嵌入页面链接处理
    if (document.body.classList.contains('embedded-page')) {
        document.addEventListener('click', function(event) {
            const link = event.target.closest('a[href]');
            if (!link || link.target || link.hasAttribute('download')) return;
            const href = link.getAttribute('href');
            if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
            const parsed = new URL(href, window.location.origin);
            if (parsed.origin !== window.location.origin) return;
            if (parsed.pathname.startsWith('/static') || parsed.pathname.startsWith('/export') || parsed.pathname.includes('/download')) return;
            event.preventDefault();
            window.location.href = withEmbeddedParam(parsed.pathname + parsed.search + parsed.hash);
        });
    }

    // 子菜单自动展开
    var currentPath = window.location.pathname;
    var submenuLists = document.querySelectorAll('.submenu-list');
    submenuLists.forEach(function(submenu) {
        var links = submenu.querySelectorAll('a');
        var shouldOpen = false;
        links.forEach(function(link) {
            if (link.getAttribute('href') === currentPath) {
                shouldOpen = true;
                link.classList.add('active');
            }
        });
        if (shouldOpen) {
            submenu.classList.add('open');
            var toggle = submenu.previousElementSibling;
            if (toggle && toggle.classList.contains('submenu-toggle')) {
                toggle.setAttribute('aria-expanded', 'true');
            }
        }
    });

    // 高亮当前菜单
    document.body.dataset.pageKey = currentPath.replace(/[^a-zA-Z0-9]+/g, '_') || 'home';
    var navLinks = document.querySelectorAll('.sidebar .nav-link');
    navLinks.forEach(function(link) {
        var href = link.getAttribute('href');
        if (href === currentPath) {
            link.classList.add('active');
        }
    });

    if (!document.body.classList.contains('embedded-page')) {
        // 启用多开菜单
        if (!isMobileViewport()) enableMultiOpenMenus();

        // 延迟恢复标签页
        if (!isMobileViewport()) {
            setTimeout(function() {
                if (window.WmsTabs) window.WmsTabs.restore();
            }, 100);
        }
    }

    // 延迟初始化表格调整
    initDocumentEntryMode();
    initMobileTableMode();
    initTrueMobileMode();

    setTimeout(function() {
        if (!isMobileViewport()) autoSetupResizableTables();
    }, 200);

    // 刷新下拉框
    if (window.WmsRefreshDropdowns) window.WmsRefreshDropdowns();

    setupSortableHeaders();
    insertGlobalActionBar();

    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') closeMobileSidebar();
    });

    window.addEventListener('resize', function() {
        if (!isMobileViewport()) closeMobileSidebar();
    });
});
