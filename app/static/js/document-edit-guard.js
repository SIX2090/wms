/* Carry the revision belonging to this document page, never to another origin. */
(function(global) {
    'use strict';
    function meta() { return document.querySelector('meta[name="document-revision"]'); }
    function tokenFor(url, method) {
        if (!/^(POST|PUT|PATCH|DELETE)$/i.test(method || 'GET')) return '';
        var element = meta();
        if (!element || !element.content) return '';
        var target;
        try { target = new URL(url, global.location.href); } catch (_) { return ''; }
        if (target.origin !== global.location.origin) return '';
        var prefixes = (element.getAttribute('data-prefixes') || '').split(',').filter(Boolean);
        return prefixes.some(function(prefix) {
            if (prefix === '/subcontract/' && /^\/subcontract\/(issue|receive)\//.test(target.pathname)) return false;
            return target.pathname.indexOf(prefix) === 0;
        }) ? element.content : '';
    }
    function headers(url, method, existing) {
        var token = tokenFor(url, method);
        if (!token) return existing;
        var result = new Headers(existing || {});
        if (!result.has('X-WMS-Document-Revision')) result.set('X-WMS-Document-Revision', token);
        return result;
    }
    function acceptResponse(response) {
        var element = meta();
        if (!element || !response) return;
        var token = response.headers && response.headers.get
            ? response.headers.get('X-WMS-Document-Revision')
            : response.getResponseHeader && response.getResponseHeader('X-WMS-Document-Revision');
        if (token) element.content = token;
    }
    document.addEventListener('submit', function(event) {
        var form = event.target;
        if (!form || !form.querySelector) return;
        var token = tokenFor(form.action, form.method);
        if (!token) return;
        var input = form.querySelector('input[name="document_revision"]');
        if (!input) {
            input = document.createElement('input');
            input.type = 'hidden'; input.name = 'document_revision'; form.appendChild(input);
        }
        input.value = token;
    }, true);
    global.WmsDocumentRevision = { tokenFor: tokenFor, headers: headers, acceptResponse: acceptResponse };
})(window);
