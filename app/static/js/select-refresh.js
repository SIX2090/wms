/* Refresh editable selects without restoring an obsolete selection or response. */
(function(global) {
    'use strict';
    var latest = new WeakMap();

    function refresh(options) {
        var targets = options.targets.filter(function(target) {
            return target.select && !target.select.disabled;
        });
        if (!targets.length) return Promise.resolve(false);
        var token = {};
        targets.forEach(function(target) { latest.set(target.select, token); });

        function current(target) {
            return latest.get(target.select) === token && !target.select.disabled && target.select.isConnected !== false;
        }

        return global.WMS.api.getRaw(options.url).then(function(response) {
            if (!targets.some(current)) return false;
            var items = options.itemsKey ? response && response[options.itemsKey] : response;
            if (!response || (response.status !== undefined && response.status !== 'success') || !Array.isArray(items)) {
                throw new Error((response && response.msg) || '刷新失败：列表数据格式不正确');
            }
            // Validate every target before mutating any dropdown.
            targets.forEach(function(target) {
                var valueKey = target.valueKey || 'id';
                if (items.some(function(item) { return !item || item[valueKey] == null || item.name == null; })) {
                    throw new Error('刷新失败：列表数据格式不正确');
                }
            });
            var applied = false;
            targets.forEach(function(target) {
                if (!current(target)) return;
                var select = target.select;
                // Read at application time: the operator may have changed it during the request.
                var selected = select.value;
                var html = '<option value="">' + global.escapeHtml(target.placeholder || '请选择') + '</option>';
                items.forEach(function(item) {
                    var value = String(item[target.valueKey || 'id']);
                    html += '<option value="' + global.escapeHtml(value) + '"' + (value === selected ? ' selected' : '') + '>' + global.escapeHtml(String(item.name)) + '</option>';
                });
                select.innerHTML = html;
                if (select.value !== selected) select.dispatchEvent(new Event('change', {bubbles: true}));
                applied = true;
            });
            return applied;
        }).catch(function(error) {
            if (targets.some(current)) throw error;
            return false;
        });
    }

    global.WMS.selectOptions = {refresh: refresh};
})(window);
