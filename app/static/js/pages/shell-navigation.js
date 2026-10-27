
    // 禁止触摸多指缩放
    document.addEventListener('touchstart', function(e) {
        if (e.touches.length > 1) {
            e.preventDefault();
        }
    }, { passive: false });

    var lastTouchEnd = 0;
    document.addEventListener('touchend', function(e) {
        var now = (new Date()).getTime();
        if (now - lastTouchEnd <= 300) {
            e.preventDefault();
        }
        lastTouchEnd = now;
    }, false);

    document.addEventListener('gesturestart', function(e) {
        e.preventDefault();
    });
    document.addEventListener('gesturechange', function(e) {
        e.preventDefault();
    });
    document.addEventListener('gestureend', function(e) {
        e.preventDefault();
    });

    // 禁止双击缩放
    document.addEventListener('dblclick', function(e) {
        e.preventDefault();
    }, { passive: false });

    // 禁止滚轮缩放
    document.addEventListener('wheel', function(e) {
        if (e.ctrlKey) {
            e.preventDefault();
        }
    }, { passive: false });

    function closeModuleMenus(exceptMenu) {
        document.querySelectorAll('.module-menu.open').forEach(function(menu) {
            if (exceptMenu && menu === exceptMenu) return;
            menu.classList.remove('open');
            var menuButton = menu.querySelector('.module-toggle');
            if (menuButton) menuButton.setAttribute('aria-expanded', 'false');
        });
    }

    function toggleModuleMenu(button) {
        var item = button ? button.closest('.module-menu') : null;
        if (!item) return;
        var shouldOpen = !item.classList.contains('open') || item.dataset.openedByHover === 'true';
        item.dataset.openedByHover = 'false';
        closeModuleMenus(item);
        item.classList.toggle('open', shouldOpen);
        button.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
    }

    document.addEventListener('mouseover', function(e) {
        var item = e.target.closest('.module-menu');
        if (!item) return;
        var hasOpenMenu = document.querySelector('.module-menu.open');
        if (!hasOpenMenu || item.classList.contains('open')) return;
        closeModuleMenus(item);
        item.classList.add('open');
        item.dataset.openedByHover = 'true';
        var menuButton = item.querySelector('.module-toggle');
        if (menuButton) menuButton.setAttribute('aria-expanded', 'true');
    });

    document.addEventListener('click', function(e) {
        if (e.target.closest('.module-flyout .flyout-link')) {
            closeModuleMenus();
            return;
        }
        if (e.target.closest('.module-menu')) return;
        closeModuleMenus();
    });

    document.addEventListener('DOMContentLoaded', function() {
        var sidebar = document.querySelector('.sidebar');
        if (!sidebar) return;
        sidebar.addEventListener('mouseleave', function() {
            window.setTimeout(function() {
                if (!document.querySelector('.module-menu:hover')) {
                    closeModuleMenus();
                }
            }, 120);
        });
    });

    // 统一日期输入框显示格式为 YYYY-MM-DD（浏览器默认可能显示 mm/dd/yyyy）
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('input[type="date"]').forEach(function(input) {
            input.setAttribute('placeholder', 'YYYY-MM-DD');
            input.setAttribute('lang', 'zh-CN');
            // 强制使用中文 locale 的日期格式显示
            if (input.value) {
                input.style.fontVariantNumeric = 'tabular-nums';
            }
        });
    });

    // P1-3 全站面包屑：依据侧边栏 flyout 菜单层级自动推导「首页 / 模块 / 当前页」。
    // 仅嵌入页（实际渲染业务内容的页）显示；首页不显示。
    document.addEventListener('DOMContentLoaded', function() {
        var nav = document.getElementById('wmsBreadcrumb');
        var list = document.getElementById('wmsBreadcrumbList');
        if (!nav || !list) return;
        var path = window.location.pathname;
        if (!path || path === '/' || path === '/index') return;
        var currentSearch = window.location.search || '';
        var links = Array.prototype.slice.call(document.querySelectorAll('.sidebar .flyout-link[href]'));
        if (!links.length) return;
        function parseHref(href) {
            var a = document.createElement('a');
            a.href = href;
            return { path: a.pathname, search: a.search || '' };
        }
        var best = null;
        var bestScore = -1;
        links.forEach(function(link) {
            var info = parseHref(link.getAttribute('href'));
            if (!info.path || info.path === '/') return;
            var score = -1;
            if (info.path === path && info.search && Array.from(new URLSearchParams(info.search)).every(function(pair) { return new URLSearchParams(currentSearch).get(pair[0]) === pair[1]; })) {
                score = 100 + info.path.length;            // 路径+查询完全匹配（如 采购入库明细）
            } else if (info.path === path && !info.search) {
                score = 50 + info.path.length;             // 纯路径匹配
            } else if (path.indexOf(info.path + '/') === 0) {
                score = 10 + info.path.length;             // 前缀匹配（详情/编辑页）
            }
            if (score > bestScore) {
                best = link;
                bestScore = score;
            }
        });
        if (!best) return;
        var flyout = best.closest('.module-flyout');
        var titleEl = flyout ? flyout.querySelector('.flyout-title') : null;
        var moduleName = titleEl ? titleEl.textContent.trim() : '';
        var pageTitle = (document.title || best.textContent).trim();
        function addItem(text, href, active) {
            var li = document.createElement('li');
            li.className = 'breadcrumb-item' + (active ? ' active' : '');
            if (active) li.setAttribute('aria-current', 'page');
            if (href) {
                var a = document.createElement('a');
                a.href = href;
                a.textContent = text;
                li.appendChild(a);
            } else {
                li.textContent = text;
            }
            list.appendChild(li);
        }
        addItem('首页', '/', false);
        if (moduleName) addItem(moduleName, null, false);
        addItem(pageTitle, null, true);
        nav.hidden = false;
    });
    