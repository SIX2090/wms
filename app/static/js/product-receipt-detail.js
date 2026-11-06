// Finished-goods detail sorting moves complete rows; it never writes a document.
(function() {
    'use strict';
    document.addEventListener('DOMContentLoaded', function() {
        const table = document.getElementById('itemTable');
        if (!table || table.dataset.businessType !== '产品入库') return;
        const body = table.tBodies[0];
        const numeric = new Set(['colStock', 'colQty', 'colPrice', 'colAmount']);
        const excluded = new Set(['seq', 'chk', 'label', 'action']);
        const collator = new Intl.Collator('zh-CN', {numeric: true, sensitivity: 'base'});
        const headers = Array.from(table.querySelectorAll('thead th[data-column-key]'));
        let sortKey = '', direction = 1;

        function value(row, key) {
            const cell = row.querySelector('[data-column-key="' + key + '"]');
            if (!cell) return null;
            const input = cell.querySelector('input:not([type="hidden"]),select,textarea');
            const raw = String(input ? input.value : (cell.dataset.value ?? cell.textContent)).trim();
            if (!raw || raw === '-') return null;
            if (!numeric.has(key)) return raw;
            const number = Number(raw.replace(/[¥￥,\s]/g, ''));
            return Number.isFinite(number) ? number : null;
        }

        function sort(header) {
            const key = header.dataset.columnKey;
            direction = sortKey === key ? -direction : 1;
            sortKey = key;
            const rows = Array.from(body.rows).filter(row => row.dataset.id || row.classList.contains('new-item-row'));
            const order = new Map(rows.map((row, index) => [row, index]));
            rows.sort(function(a, b) {
                const left = value(a, key), right = value(b, key);
                if (left === null || right === null) return left === right ? order.get(a) - order.get(b) : (left === null ? 1 : -1);
                const compared = numeric.has(key) ? left - right : collator.compare(left, right);
                return direction * compared || order.get(a) - order.get(b);
            });
            rows.forEach(function(row, index) {
                body.appendChild(row);
                const number = row.querySelector('.row-num');
                if (number) number.textContent = String(index + 1);
            });
            headers.forEach(function(th) {
                if (excluded.has(th.dataset.columnKey)) return;
                th.setAttribute('aria-sort', th === header ? (direction === 1 ? 'ascending' : 'descending') : 'none');
                th.classList.remove('sorted-asc', 'sorted-desc');
                if (th === header) th.classList.add(direction === 1 ? 'sorted-asc' : 'sorted-desc');
                th.querySelector('.cb-sort-indicator').textContent = th === header ? (direction === 1 ? ' ↑' : ' ↓') : ' ↕';
            });
        }

        headers.forEach(function(header) {
            if (excluded.has(header.dataset.columnKey)) return;
            header.classList.add('cb-detail-sortable');
            header.tabIndex = 0;
            header.setAttribute('aria-sort', 'none');
            const indicator = document.createElement('span');
            indicator.className = 'cb-sort-indicator';
            indicator.setAttribute('aria-hidden', 'true');
            indicator.textContent = ' ↕';
            header.appendChild(indicator);
            header.addEventListener('click', function(event) {
                if (!event.target.closest('button,input,.resize-handle,.cb-col-resizer')) sort(header);
            });
            header.addEventListener('keydown', function(event) {
                if (event.target !== header) return;
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    sort(header);
                }
            });
        });
    });
})();
