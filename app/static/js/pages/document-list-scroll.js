/* Restore only this account's exact list history entry, never form values. */
(function () {
    'use strict';
    const account = document.currentScript.dataset.userId;
    const key = account + ':' + location.pathname + location.search;
    const selectors = ['.main-content', '.embedded-content', '.table-responsive-wrapper'];
    let pending = false;

    function elements() {
        return [document.scrollingElement].concat(selectors.flatMap(function (selector) {
            return Array.from(document.querySelectorAll(selector));
        }));
    }

    function save() {
        pending = false;
        const position = elements().map(function (element) {
            return {top: element.scrollTop, left: element.scrollLeft};
        });
        try {
            history.replaceState(Object.assign({}, history.state, {
                wmsDocumentListScroll: {key: key, position: position}
            }), '');
        } catch (_) { /* Unavailable history must not block list navigation. */ }
    }

    function restore(saved) {
        saved = saved || (history.state && history.state.wmsDocumentListScroll);
        if (!saved || saved.key !== key || !Array.isArray(saved.position)) return;
        elements().forEach(function (element, index) {
            const point = saved.position[index];
            if (!point || !Number.isFinite(point.top) || !Number.isFinite(point.left)) return;
            // Late column/layout sizing must not anchor a restored entry to another row.
            element.style.overflowAnchor = 'none';
            element.scrollTop = point.top;
            element.scrollLeft = point.left;
        });
    }

    document.addEventListener('scroll', function () {
        if (!pending) {
            pending = true;
            requestAnimationFrame(save);
        }
    }, true);
    window.addEventListener('pagehide', save);
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) restore();
    });
    const navigation = performance.getEntriesByType('navigation')[0];
    if (navigation && navigation.type === 'back_forward') {
        const saved = history.state && history.state.wmsDocumentListScroll;
        requestAnimationFrame(function () { requestAnimationFrame(function () { restore(saved); }); });
    }
})();
