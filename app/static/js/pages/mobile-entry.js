/* Select the H5 workbench on a phone; never change credentials or business requests. */
(function () {
    'use strict';
    if (window.self !== window.top || !window.matchMedia || !window.matchMedia('(max-width: 767px)').matches) return;
    var current = new URL(window.location.href);
    if (current.searchParams.get('embedded') === '1' || current.searchParams.get('desktop') === '1') return;
    if (current.pathname === '/login') {
        var next = document.querySelector('form input[name="next"]');
        if (next && !next.value.trim()) next.value = '/mobile';
        return;
    }
    if (current.pathname !== '/') return;
    if (Array.from(current.searchParams.keys()).some(function (key) { return key !== 'mobile'; })) return;
    window.location.replace('/mobile');
})();
