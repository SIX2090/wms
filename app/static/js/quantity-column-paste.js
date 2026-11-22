/* Apply a spreadsheet column to existing document lines in their displayed order. */
(function (WMS) {
    'use strict';

    WMS.bindQuantityColumnPaste = function (bodyId, selector, enabled, stocktake = false) {
        const body = document.getElementById(bodyId);
        body.addEventListener('paste', function (event) {
            const input = event.target;
            if (!input.matches(selector) || input.readOnly || input.disabled) return;
            const text = event.clipboardData?.getData('text/plain');
            if (!text || !/[\t\r\n]/.test(text)) return;
            event.preventDefault();
            if (!enabled()) return;
            if (text.includes('\t')) {
                showToast('请只复制一列数量。', 'warning');
                return;
            }

            // Excel terminates its TSV records with CRLF. Remove only the final separator.
            const values = text.replace(/\r\n?/g, '\n').replace(/\n$/, '').split('\n');
            const rows = Array.from(body.rows);
            const start = rows.indexOf(input.closest('tr'));
            const targets = [];
            for (const [offset, raw] of values.entries()) {
                const row = rows[start + offset];
                const field = row?.querySelector(selector);
                const rowNumber = start + offset + 1;
                if (!field || field.readOnly || field.disabled || !row.querySelector('.material-code')?.value.trim()) {
                    showToast('单据第 ' + rowNumber + ' 行没有可填写数量的物料，本次未粘贴。', 'warning');
                    return;
                }
                const value = raw.trim();
                const decimal = /^(?:\d+(?:\.\d{1,2})?|\.\d{1,2})$/.test(value);
                if (!(stocktake && value === '') &&
                    (!decimal || !Number.isFinite(Number(value)) || (!stocktake && Number(value) <= 0))) {
                    const rule = stocktake ? '请填零或正数，未盘可留空' : '请填大于零的数量';
                    showToast('单据第 ' + rowNumber + ' 行数量无效，' + rule + '，最多两位小数。本次未粘贴。', 'warning');
                    return;
                }
                targets.push({field, value});
            }
            for (const {field, value} of targets) {
                field.value = value;
                field.dispatchEvent(new Event('input', {bubbles: true}));
            }
            showToast('已填写第 ' + (start + 1) + ' 至 ' + (start + targets.length) + ' 行数量。', 'success');
        });
    };
})(window.WMS);
