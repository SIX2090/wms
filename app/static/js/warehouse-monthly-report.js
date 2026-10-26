/* 自然月筛选：兼容旧日期链接，查询与导出共用月份参数。 */
(function () {
    'use strict';
    function monthText(value) {
        return [value.getFullYear(), String(value.getMonth() + 1).padStart(2, '0')].join('-');
    }
    function applyRange(kind, document, now = new Date()) {
        const end = new Date(now.getFullYear(), now.getMonth(), 1);
        const start = new Date(end);
        if (kind === 'previous') { start.setMonth(start.getMonth() - 1); end.setMonth(end.getMonth() - 1); }
        if (kind === 'year') start.setMonth(0);
        document.getElementById('start_month').value = monthText(start);
        document.getElementById('end_month').value = monthText(end);
    }
    function initialise(document, search, changed) {
        const params = new URLSearchParams(search);
        const current = monthText(new Date());
        ['start', 'end'].forEach(key => {
            const field = document.getElementById(key + '_month');
            field.value = params.get(key + '_month') || (params.get(key + '_date') || '').slice(0, 7) || current;
        });
        document.querySelectorAll('[data-month-range]').forEach(button => {
            button.addEventListener('click', () => { applyRange(button.dataset.monthRange, document); changed(); });
        });
    }
    window.WMSWarehouseMonthly = { initialise, applyRange };
}());
