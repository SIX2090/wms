// Keep a document action locked through confirmation and its complete request chain.
(function(global) {
    'use strict';
    var active = Object.create(null);
    global.WMS = global.WMS || {};
    global.WMS.runDocumentAction = function(key, action) {
        if (active[key]) return active[key];
        var buttons = Array.from(global.document.querySelectorAll(
            'button[data-document-action="' + key + '"]'));
        var states = buttons.map(function(button) {
            return { disabled: button.disabled, busy: button.getAttribute('aria-busy') };
        });
        buttons.forEach(function(button) {
            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
        });
        active[key] = Promise.resolve().then(action).catch(function(error) {
            if (typeof global.showToast === 'function') {
                global.showToast('操作失败：' + ((error && error.message) || '请稍后重试'), 'danger');
            }
        }).finally(function() {
            buttons.forEach(function(button, index) {
                button.disabled = states[index].disabled;
                if (states[index].busy === null) button.removeAttribute('aria-busy');
                else button.setAttribute('aria-busy', states[index].busy);
            });
            delete active[key];
        });
        return active[key];
    };
})(window);
