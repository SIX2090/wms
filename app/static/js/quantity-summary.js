/** Live, unsaved document quantities. Reads entry rows only; never writes business data. */
(function(global) {
    'use strict';
    var WMS = global.WMS = global.WMS || {};

    function refresh(tableId) {
        document.querySelectorAll('[data-quantity-summary]').forEach(function(summary) {
            if (tableId && summary.dataset.quantitySummary !== tableId) return;
            var table = document.getElementById(summary.dataset.quantitySummary);
            if (!table) return;
            var total = 0;
            table.querySelectorAll('tbody tr').forEach(function(row) {
                var code = row.querySelector(summary.dataset.materialSelector);
                if (code && !String(code.value || '').trim()) return;
                var cell = row.querySelector(summary.dataset.quantitySelector);
                if (!cell) return;
                // Existing detail cells become inputs while editing. Prefer that
                // unsaved input over the rendered cell text/server-side data-value.
                var input = cell.querySelector ? cell.querySelector('input') : null;
                var raw = input ? input.value : ('value' in cell ? cell.value :
                    (cell.dataset && cell.dataset.value !== undefined ? cell.dataset.value : cell.textContent));
                var value = Number(String(raw).trim());
                if (Number.isFinite(value)) total += value;
            });
            var output = summary.querySelector('[data-quantity-value]');
            var formatted = total.toLocaleString('zh-CN', {
                minimumFractionDigits: 2, maximumFractionDigits: 4
            });
            if (output.textContent !== formatted) output.textContent = formatted;
        });
    }

    WMS.refreshQuantityTotals = refresh;
    function init() {
        document.querySelectorAll('[data-quantity-summary]').forEach(function(summary) {
            var id = summary.dataset.quantitySummary;
            var table = document.getElementById(id);
            if (!table) return;
            var update = function() { refresh(id); };
            table.addEventListener('input', update);
            table.addEventListener('change', update);
            // Row insertion, copy, deletion, import and restored drafts all change the grid.
            var body = table.querySelector('tbody');
            if (body) new MutationObserver(update).observe(body, {
                childList: true, subtree: true, characterData: true
            });
            if (table.closest('form')) table.closest('form').addEventListener('reset', function() {
                global.setTimeout(update, 0);
            });
            update();
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})(window);
