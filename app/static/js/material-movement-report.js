/* 物料收发存的数量按单位展示，避免把件、米等直接相加。 */
(function () {
    'use strict';
    function formatUnitTotal(summary, key) {
        const totals = summary && Array.isArray(summary.unit_totals) ? summary.unit_totals : [];
        return totals.length ? totals.map(item =>
            Number(item[key] || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 }) + ' ' + (item.unit || '未设单位')
        ).join(' / ') : '0';
    }
    window.WMSMaterialMovement = { formatUnitTotal };
}());
