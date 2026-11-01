/** Two-decimal entry rounding, matching the backend's ROUND_HALF_UP contract. */
(function(global) {
    'use strict';
    var WMS = global.WMS = global.WMS || {};
    // Decimal formatting avoids toFixed's binary tie errors (e.g. 1.005 -> 1.00).
    var formatter = new Intl.NumberFormat('en-US', {
        useGrouping: false, minimumFractionDigits: 2, maximumFractionDigits: 2
    });

    WMS.normalizeDecimalInput = function(input, label) {
        if (!input || input.readOnly || input.disabled) return;
        var original = String(input.value).trim();
        if (!original) return;
        var value = Number(original);
        if (!Number.isFinite(value)) return;
        var rounded = formatter.format(value);
        if (Number(rounded) !== value) {
            input.value = rounded;
            if (typeof global.showToast === 'function') {
                global.showToast((label || '数量') + '已按两位小数四舍五入：' +
                    original + ' → ' + rounded, 'warning', 5000);
            }
        }
    };
})(window);
