// The migrated pages keep normal shell navigation without inline handlers.
(function() {
    'use strict';
    var actions = {
        toggleMobileSidebar: function() { window.toggleMobileSidebar(); },
        closeMobileSidebar: function() { window.closeMobileSidebar(); },
        toggleModuleMenu: function(node) { window.toggleModuleMenu(node); },
        toggleSubmenu: function(node) { window.toggleSubmenu(node); }
    };
    document.addEventListener('click', function(event) {
        var node = event.target.closest('[data-material-shell-action]');
        if (!node) return;
        var name = node.getAttribute('data-material-shell-action');
        if (!Object.prototype.hasOwnProperty.call(actions, name)) return;
        event.preventDefault();
        actions[name](node);
    });
})();
