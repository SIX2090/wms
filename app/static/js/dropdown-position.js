/* Keep document picker menus inside the current window (including tab iframes). */
(function (window, document) {
    'use strict';
    window.WMS = window.WMS || {};
    let active = null;
    const preferredWidths = new WeakMap();

    window.WMS.positionDropdown = function (input, menu, options) {
        if (!input || !menu) return;
        const settings = options || {};
        const rect = input.getBoundingClientRect();
        const margin = 8;
        const gap = settings.gap === undefined ? 5 : settings.gap;
        const limit = settings.maxHeight || 280;
        const below = Math.max(0, window.innerHeight - rect.bottom - gap - margin);
        const above = Math.max(0, rect.top - gap - margin);
        const upward = below < limit && above > below;
        const preferredWidth = settings.minWidth || preferredWidths.get(menu) ||
            parseFloat(window.getComputedStyle(menu).minWidth) || menu.offsetWidth || rect.width;
        preferredWidths.set(menu, preferredWidth);
        const width = Math.min(Math.max(rect.width, preferredWidth), Math.max(0, window.innerWidth - margin * 2));
        menu.style.position = 'fixed';
        menu.style.boxSizing = 'border-box';
        menu.style.minWidth = '0';
        menu.style.width = width + 'px';
        menu.style.left = Math.max(margin, Math.min(rect.left, window.innerWidth - margin - width)) + 'px';
        menu.style.right = 'auto';
        menu.style.maxHeight = Math.min(limit, upward ? above : below) + 'px';
        menu.style.overflowY = 'auto';
        menu.style.top = upward ? 'auto' : (rect.bottom + gap) + 'px';
        menu.style.bottom = upward ? (window.innerHeight - rect.top + gap) + 'px' : 'auto';
        menu.style.visibility = rect.bottom < margin || rect.top > window.innerHeight - margin ? 'hidden' : '';
        active = {input: input, menu: menu, options: Object.assign({}, settings, {minWidth: preferredWidth})};
    };

    function reposition(event) {
        if (!active) return;
        if (!active.input.isConnected || !active.menu.isConnected) {
            active = null;
            return;
        }
        // Scrolling candidates must not move the menu or the document underneath.
        if (event && event.type === 'scroll' && active.menu.contains(event.target)) return;
        if (!active.menu.getClientRects().length) return;
        window.WMS.positionDropdown(active.input, active.menu, active.options);
    }
    document.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
})(window, document);
