/* H5 presentation state only: never changes business requests or credentials. */
(function () {
    'use strict';
    if (!document.body.classList.contains('mobile-app-page')) return;
    document.addEventListener('click', function (event) {
        var link = event.target.closest && event.target.closest('a[href]');
        if (!link || link.hasAttribute('download') || link.hasAttribute('data-mobile-desktop') || link.target) return;
        var href = link.getAttribute('href');
        if (!href || href.charAt(0) === '#') return;
        var target;
        try { target = new URL(href, window.location.href); } catch (error) { return; }
        if (target.origin !== window.location.origin || !/^https?:$/.test(target.protocol)) return;
        if (/^\/(?:api|static)(?:\/|$)/.test(target.pathname) || /\/(?:download|print|export)[^/]*(?:\/|$)/.test(target.pathname)) return;
        if (['token', 'signature', 'sig'].some(function (key) { return target.searchParams.has(key); })) return;
        target.searchParams.set('mobile', '1');
        link.href = target.pathname + target.search + target.hash;
    });
    document.querySelectorAll('form').forEach(function (form) {
        if ((form.method || 'get').toLowerCase() !== 'get' || form.querySelector('[name="mobile"]')) return;
        var action;
        try { action = new URL(form.action || window.location.href, window.location.href); } catch (error) { return; }
        if (action.origin !== window.location.origin || /^\/(?:api|static)(?:\/|$)/.test(action.pathname) || /\/(?:download|print|export)[^/]*(?:\/|$)/.test(action.pathname)) return;
        var input = document.createElement('input');
        input.type = 'hidden'; input.name = 'mobile'; input.value = '1'; form.appendChild(input);
    });
})();
