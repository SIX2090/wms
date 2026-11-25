/* Complete the paginated material cache before replacing any existing candidates. */
(function(global) {
    'use strict';
    var active = new WeakMap();
    var pageSize = 2000;

    async function refresh(target, warehouse) {
        var ticket = {};
        active.set(target, ticket);
        var current = function() { return active.get(target) === ticket; };
        var found = [], seen = new Set(), total = null, pages = null;
        try {
            for (var page = 1; ; page++) {
                var response = await global.WMS.api.getRaw('/material/api/all?page=' + page + '&per_page=' + pageSize +
                    (warehouse ? '&warehouse=' + encodeURIComponent(warehouse) : ''));
                if (!current()) return false;
                if (!response || response.status !== 'success' || !Array.isArray(response.materials) ||
                    !Number.isSafeInteger(response.total) || response.total < 0 ||
                    response.page !== page || response.per_page !== pageSize ||
                    response.pages !== Math.ceil(response.total / pageSize)) {
                    throw new Error('物料分页数据不完整，请重新刷新');
                }
                if (total === null) { total = response.total; pages = response.pages; }
                if (response.total !== total || response.pages !== pages ||
                    response.materials.length !== Math.max(0, Math.min(pageSize, total - (page - 1) * pageSize))) {
                    throw new Error('刷新期间物料列表已变化，请重新刷新');
                }
                response.materials.forEach(function(material) {
                    if (!material || material.id == null || typeof material.code !== 'string' ||
                        typeof material.name !== 'string' || seen.has(String(material.id))) {
                        throw new Error('物料分页包含无效或重复记录，请重新刷新');
                    }
                    seen.add(String(material.id));
                    found.push(material);
                });
                if (page >= pages) break;
            }
            // Preserve already-referenced draft materials (e.g. recently deactivated items)
            // so existing rows remain savable after a cache refresh.
            var preserved = [];
            if (typeof document !== 'undefined' && typeof document.querySelectorAll === 'function') {
                var usedCodes = new Set();
                document.querySelectorAll('.material-code').forEach(function(input) {
                    var code = String(input.value || '').trim().toLowerCase();
                    if (code) usedCodes.add(code);
                });
                if (usedCodes.size) {
                    target.forEach(function(material) {
                        if (!material || material.id == null) return;
                        var codeKey = String(material.code || '').trim().toLowerCase();
                        if (usedCodes.has(codeKey) && !seen.has(String(material.id))) {
                            seen.add(String(material.id));
                            preserved.push(material);
                        }
                    });
                }
            }
            // Commit only a complete latest result, keeping the array identity used by the page.
            target.length = 0;
            found.forEach(function(material) { target.push(material); });
            preserved.forEach(function(material) { target.push(material); });
            return true;
        } catch (error) {
            if (current()) throw error;
            return false;
        } finally {
            if (current()) active.delete(target);
        }
    }

    function warehouseFromForm() {
        var field = document.querySelector('[name="warehouse_id"], [name="warehouse"], [name="from_warehouse"], select[name="from_location"]');
        if (!field || !field.value) return '';
        var option = field.selectedOptions && field.selectedOptions[0];
        return option ? option.textContent.trim() : field.value;
    }

    function bindWarehouse(target) {
        var field = document.querySelector('[name="warehouse_id"], [name="warehouse"], [name="from_warehouse"], select[name="from_location"]');
        if (!field || !field.addEventListener || field.dataset && field.dataset.stockScopeBound) return;
        if (field.dataset) field.dataset.stockScopeBound = 'true';
        field.addEventListener('change', async function() {
            var warehouse = warehouseFromForm();
            if (!warehouse) {
                document.querySelectorAll('.material-stock').forEach(function(input) { input.value = ''; });
                return;
            }
            document.querySelectorAll('.material-stock').forEach(function(input) { input.value = ''; });
            try {
                if (!await refresh(target, warehouse)) return;
                document.querySelectorAll('.material-code').forEach(function(input) {
                    var material = target.find(function(item) { return item.code === input.value.trim(); });
                    var row = input.closest('tr');
                    if (!row || !material) return;
                    var stock = row.querySelector('.material-stock');
                    var system = row.querySelector('.system-stock');
                    var displayStock = system && !Number(material.stock) ? '' : Number(material.stock || 0).toFixed(2);
                    if (stock) stock.value = displayStock;
                    if (row.dataset && row.dataset.systemStockFrozen !== 'true') {
                        if (system) system.value = displayStock;
                        var actual = row.querySelector('.actual-stock');
                        if (actual && row.dataset.counted !== 'true') actual.value = '';
                        var difference = row.querySelector('.line-diff');
                        if (difference && actual && system) difference.value = actual.value === '' ? '' : (Number(actual.value) - Number(system.value)).toFixed(2);
                    }
                });
                if (typeof global.updateCheckTotals === 'function' && typeof document.querySelectorAll === 'function') {
                    var checkRows = document.querySelectorAll('#docTableBody tr');
                    if (checkRows && checkRows.length) global.updateCheckTotals(checkRows);
                }
            } catch (error) {
                if (typeof global.showToast === 'function') global.showToast('仓库库存刷新失败，请重试：' + error.message, 'danger');
            }
        });
    }

    global.WMS.materialCache = {
        refresh: refresh,
        warehouseFromForm: warehouseFromForm,
        bindWarehouse: bindWarehouse,
        isRefreshing: function(target) { return active.has(target); }
    };
})(window);
