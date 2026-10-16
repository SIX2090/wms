/* Keyboard interaction shared by document material pickers. */
(function (window) {
    'use strict';
    window.WMS = window.WMS || {};
    window.WMS.MaterialPicker = {
        bindEntryRow: function (row, selectors, nextRow) {
            selectors.forEach(function (selector, index) {
                const input = row.querySelector(selector);
                if (!input) return;
                input.addEventListener('keydown', function (event) {
                    if (event.key !== 'Enter' || event.defaultPrevented || event.isComposing ||
                        event.keyCode === 229 || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey ||
                        input.disabled || input.readOnly) return;
                    event.preventDefault();
                    const target = selectors.slice(index + 1).map(function (s) { return row.querySelector(s); })
                        .find(function (field) {
                            return field && !field.disabled && !field.readOnly && field.getClientRects().length;
                        });
                    const destination = target || nextRow();
                    if (destination) {
                        destination.focus();
                        if (destination.select) destination.select();
                        // Column-layout observers move new cells and can blur the input.
                        // Restore only a lost focus, never replace another chosen control.
                        if (window.requestAnimationFrame) window.requestAnimationFrame(function () {
                            const doc = destination.ownerDocument;
                            if (destination.isConnected && doc && doc.activeElement === doc.body) {
                                destination.focus();
                                if (destination.select) destination.select();
                            }
                        });
                    }
                });
            });
        },
        handleKeydown: function (event, dropdown, choose) {
            // Confirming Chinese text must not select a material or move focus.
            if (event.isComposing || event.keyCode === 229) return true;
            if (!dropdown || dropdown.style.display !== 'block') return false;
            if (event.key === 'Escape') {
                event.preventDefault();
                dropdown.style.display = 'none';
                return true;
            }
            if (!['ArrowDown', 'ArrowUp', 'Enter'].includes(event.key)) return false;
            const items = Array.from(dropdown.querySelectorAll('.material-dropdown-item[data-code]'))
                .filter(function (item) { return item.dataset.code && item.dataset.empty !== '1'; });
            if (!items.length) return false;
            event.preventDefault();
            let index = items.findIndex(function (item) { return item.classList.contains('active'); });
            if (event.key === 'Enter') {
                choose(items[index < 0 ? 0 : index]);
                return true;
            }
            if (index < 0) index = event.key === 'ArrowDown' ? -1 : items.length;
            index = event.key === 'ArrowDown'
                ? Math.min(index + 1, items.length - 1)
                : Math.max(index - 1, 0);
            items.forEach(function (item) { item.classList.remove('active'); });
            items[index].classList.add('active');
            items[index].scrollIntoView({ block: 'nearest' });
            return true;
        }
    };
})(window);
