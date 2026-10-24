/* Atomically refresh full master-data arrays without applying obsolete responses. */
(function(global) {
    'use strict';
    var latest = new WeakMap();

    function refresh(target, url) {
        var token = {};
        latest.set(target, token);
        return global.WMS.api.getRaw(url).then(function(items) {
            if (latest.get(target) !== token) return false;
            var ids = new Set();
            if (!Array.isArray(items) || items.some(function(item) {
                if (!item || item.id == null || String(item.id) === '' || typeof item.name !== 'string') return true;
                var id = String(item.id);
                if (ids.has(id)) return true;
                ids.add(id);
                return false;
            })) {
                throw new Error((items && items.msg) || '刷新失败：列表数据格式不正确');
            }
            // Keep the same array: search handlers close over this reference.
            target.length = 0;
            items.forEach(function(item) { target.push(item); });
            return true;
        }).catch(function(error) {
            if (latest.get(target) !== token) return false;
            throw error;
        });
    }

    global.WMS = global.WMS || {};
    global.WMS.listCache = {refresh: refresh};
})(window);
