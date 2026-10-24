/** Subcontract issue/receive material identity and guarded draft saves. */
(function(global) {
    'use strict';
    var WMS = global.WMS = global.WMS || {};

    function choose(materials, text) {
        var keyword = text.trim().toLowerCase();
        if (!keyword) return null;
        var matches = materials.filter(function(material) {
            return ['code', 'name', 'spec'].some(function(key) {
                return typeof material[key] === 'string' && material[key].toLowerCase().includes(keyword);
            });
        });
        var codes = matches.filter(function(material) { return typeof material.code === 'string' && material.code.toLowerCase() === keyword; });
        if (codes.length) return codes.length === 1 ? codes[0] : null;
        var names = matches.filter(function(material) { return (material.name || '').toLowerCase() === keyword; });
        if (names.length) return names.length === 1 ? names[0] : null;
        return matches.length === 1 ? matches[0] : null;
    }

    function createSaver(options) {
        var form = options.form;
        var modal = options.modal;
        var button = options.button;
        var revision = 0;
        var pending = false;
        function changed() { revision++; }
        form.addEventListener('input', changed);
        form.addEventListener('change', changed);
        modal.addEventListener('hide.bs.modal', changed);
        modal.addEventListener('hidden.bs.modal', changed);

        return async function() {
            if (pending) return;
            pending = true;
            var completed = false;
            var wasDisabled = button.disabled;
            button.disabled = true;
            try {
                options.resolveInputs();
                if (!options.warehouse.value) {
                    global.showToast('请选择仓库', 'danger');
                    return;
                }
                var data = new FormData(form);
                var signature = JSON.stringify(Array.from(data.entries()));
                var expectedRevision = revision;
                var inputs = Array.from(form.querySelectorAll('.material-input'));
                function assertCurrent() {
                    var currentInputs = Array.from(form.querySelectorAll('.material-input'));
                    if (revision !== expectedRevision || form.isConnected === false || modal.isConnected === false ||
                        document.getElementById(form.id) !== form ||
                        currentInputs.length !== inputs.length || inputs.some(function(input, index) {
                            return input !== currentInputs[index] || input.isConnected === false;
                        }) || JSON.stringify(Array.from(new FormData(form).entries())) !== signature) {
                        throw new Error('表单已变更或窗口已关闭，请确认物料后重新保存');
                    }
                }
                var ids = data.getAll('material_id');
                var codes = data.getAll('material_code');
                if (ids.length !== codes.length) throw new Error('物料明细格式不正确，请重新打开单据');
                var unresolved = [];
                codes.forEach(function(code, index) {
                    var trimmed = code.trim();
                    if (!ids[index] && trimmed) {
                        if (trimmed.length > 100) throw new Error('第' + (index + 1) + '行物料编码过长，请重新选择物料');
                        if (!unresolved.includes(trimmed)) unresolved.push(trimmed);
                    }
                });
                var resolved = new Map();
                var seenIds = new Set();
                for (var offset = 0; offset < unresolved.length; offset += 200) {
                    assertCurrent();
                    var batch = unresolved.slice(offset, offset + 200);
                    var query = batch.map(function(code) { return 'code=' + encodeURIComponent(code); }).join('&');
                    var items = await WMS.api.get('/material/api/by_codes?' + query);
                    assertCurrent();
                    if (!Array.isArray(items)) throw new Error('物料查询结果格式不正确，请重试');
                    items.forEach(function(item) {
                        if (!item || !Number.isSafeInteger(item.id) || item.id <= 0 ||
                            typeof item.code !== 'string' || typeof item.name !== 'string' ||
                            !batch.includes(item.code) || resolved.has(item.code) || seenIds.has(item.id)) {
                            throw new Error('物料查询结果格式不正确，请重试');
                        }
                        resolved.set(item.code, item.id);
                        seenIds.add(item.id);
                    });
                    if (batch.some(function(code) { return !resolved.has(code); })) {
                        throw new Error('存在未选定的物料，请从候选中选择或输入完整物料编码后重新保存');
                    }
                }
                assertCurrent();
                // Keep the user's DOM unchanged while resolving; replace IDs only in this verified snapshot.
                data.delete('material_id');
                ids.forEach(function(id, index) {
                    data.append('material_id', id || resolved.get(codes[index].trim()) || '');
                });
                var result = await WMS.api.postRaw(options.url, data);
                completed = !!(result && result.status === 'success');
                options.onResult(result);
            } catch (error) {
                global.showToast('新增失败：' + (error.message || '请稍后重试'), 'danger');
            } finally {
                if (!completed) {
                    pending = false;
                    button.disabled = wasDisabled;
                }
            }
        };
    }

    WMS.subcontractMaterialSelection = { choose: choose, createSaver: createSaver };
})(window);
