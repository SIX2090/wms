/* Keyboard interaction shared by document material pickers. */
(function (window) {
    'use strict';
    window.WMS = window.WMS || {};
    window.WMS.MaterialPicker = {
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
