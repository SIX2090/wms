/* MATERIAL-MERGE-HUMAN-001: selection and identity decisions belong to the operator. */
(function () {
    'use strict';
    var state = {source: null, target: null, preview: null, page: 1, pages: 0,
        busy: false, searchSeq: 0, previewSeq: 0, initialized: false};
    function node(id) { return document.getElementById(id); }
    function error(message) {
        node('mergeError').textContent = message || '';
        node('mergeError').hidden = !message;
    }
    function sync() {
        node('mergeDirection').textContent = '被合并：' + (state.source ? state.source.code : '')
            + ' → 保留：' + (state.target ? state.target.code : '请从下方选择');
        node('mergeExecuteBtn').disabled = state.busy || !state.preview || !node('mergeHumanConfirmed').checked;
        node('mergeExecuteBtn').textContent = state.busy ? '正在合并…' : '确认合并';
        node('mergeSwapBtn').disabled = state.busy || !state.target;
        node('mergePrevBtn').disabled = state.busy || state.page <= 1;
        node('mergeNextBtn').disabled = state.busy || state.page >= state.pages;
        node('mergeSearchBtn').disabled = state.busy;
        node('mergeSearch').disabled = state.busy;
        node('mergeHumanConfirmed').disabled = state.busy;
        node('materialMergeModal').querySelectorAll('[data-bs-dismiss], [data-merge-select]').forEach(function (button) {
            button.disabled = state.busy;
        });
    }
    function invalidate() {
        state.preview = null;
        state.previewSeq += 1;
        node('mergeHumanConfirmed').checked = false;
        node('mergePreview').hidden = true;
        error('');
        sync();
    }
    function cell(row, value) {
        var element = document.createElement('td');
        element.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
        row.appendChild(element);
        return element;
    }
    function status(value) { return value === 'inactive' ? '停用' : '启用'; }
    function preview() {
        invalidate();
        if (!state.target) return;
        var seq = state.previewSeq, source = state.source, target = state.target;
        WMS.api.postRaw('/material/merge_preview', {source_code: source.code, target_code: target.code, manual_review: true})
            .then(function (response) {
                if (seq !== state.previewSeq) return;
                if (!response || response.status !== 'success') {
                    error(response && response.msg || '无法预览合并影响');
                    return;
                }
                var data = response.data, body = node('mergeComparison'), differences = [];
                if (!data || String(data.source.code) !== String(source.code) || String(data.target.code) !== String(target.code)) {
                    error('预览与选择的物料不一致，请重新选择。');
                    return;
                }
                body.replaceChildren();
                [['code', '编码'], ['name', '名称'], ['spec', '规格'], ['brand', '品牌'],
                    ['unit', '库存单位'], ['status', '状态'], ['stock', '库存数量']].forEach(function (field) {
                    var row = document.createElement('tr'), key = field[0];
                    cell(row, field[1]);
                    cell(row, key === 'status' ? status(data.source[key]) : data.source[key]);
                    cell(row, key === 'status' ? status(data.target[key]) : data.target[key]);
                    if (['name', 'spec', 'brand'].indexOf(key) >= 0 && String(data.source[key] || '') !== String(data.target[key] || '')) {
                        row.className = 'table-warning';
                        differences.push(field[1]);
                    }
                    body.appendChild(row);
                });
                node('mergeDifferences').textContent = differences.length ? '差异提示：' + differences.join('、') + '不同，请人工判断是否同一种物料。' : '档案属性一致，仍需人工判断并确认。';
                var labels = {adjustment_order_item: '调整单明细', after_sale_out_order_item: '售后出库明细',
                    ai_document_item: 'AI草稿明细', bom_item: 'BOM明细', in_order_item: '入库明细',
                    inventory_check_item: '盘点明细', inventory_check_scan_item: '扫码盘点明细', material_image: '物料图片',
                    opening_stock: '期初库存', out_order_item: '出库明细', production_requisition_item: '领料明细',
                    purchase_order_item: '采购订单明细', purchase_request_item: '采购申请明细', sales_order_item: '销售订单明细',
                    stock_transaction: '库存流水', subcontract_issue_item: '委外发料明细', subcontract_item: '委外订单明细',
                    subcontract_receive_item: '委外收料明细', transfer_order_item: '调拨明细', location_inventory: '库存账',
                    ai_material_alias: '旧编码别名'};
                var impacts = Object.keys(data.tables || {}).map(function (key) { return (labels[key] || '其他关联记录') + '：' + data.tables[key] + '行'; });
                node('mergeImpact').textContent = '合并后库存：' + data.source.stock + ' + ' + data.target.stock + ' = ' + data.stock_after
                    + ' ' + (data.target.unit || '') + '；影响 ' + data.total_rows + ' 行记录。' + impacts.join('；');
                state.preview = data;
                node('mergePreview').hidden = false;
                sync();
            }).catch(function (reason) {
                if (seq === state.previewSeq) error('预览失败：' + (reason.message || '请重试'));
            });
    }
    function choose(material) {
        if (state.busy || Number(material.id) === Number(state.source.id)) return;
        state.target = material;
        preview();
    }
    function search(page) {
        if (state.busy) return;
        var seq = ++state.searchSeq;
        node('mergePrevBtn').disabled = true;
        node('mergeNextBtn').disabled = true;
        node('mergePageInfo').textContent = '正在查询…';
        node('mergeCandidates').replaceChildren();
        var query = new URLSearchParams({kw: node('mergeSearch').value.trim(), page: String(page), source_id: String(state.source.id)});
        WMS.api.getRaw('/material/merge_candidates?' + query.toString()).then(function (response) {
            if (seq !== state.searchSeq) return;
            if (!response || response.status !== 'success') throw new Error(response && response.msg || '查询失败');
            state.page = response.page;
            state.pages = response.total_pages;
            node('mergePageInfo').textContent = '共 ' + response.total + ' 条，第 ' + (response.total_pages ? response.page : 0) + '/' + response.total_pages + ' 页';
            response.data.forEach(function (material) {
                var row = document.createElement('tr');
                ['code', 'name', 'spec', 'brand', 'unit'].forEach(function (key) { cell(row, material[key]); });
                cell(row, status(material.status));
                var action = cell(row, ''), button = document.createElement('button');
                action.replaceChildren();
                button.type = 'button'; button.className = 'btn btn-sm btn-outline-primary';
                button.textContent = '保留此物料'; button.dataset.mergeSelect = String(material.id);
                button.addEventListener('click', function () { choose(material); });
                action.appendChild(button); node('mergeCandidates').appendChild(row);
            });
            sync();
        }).catch(function (reason) {
            if (seq === state.searchSeq) { node('mergePageInfo').textContent = '查询失败'; error(reason.message || '查询失败'); }
        });
    }
    function execute() {
        if (state.busy || !state.preview || !node('mergeHumanConfirmed').checked) return;
        var source = state.source, target = state.target;
        state.busy = true; sync(); error('');
        WMS.api.postRaw('/material/' + source.id + '/merge', {target_code: target.code,
            keep_alias: true, confirm: true, identity_confirmed: true}).then(function (response) {
                if (!response || response.status !== 'success') throw new Error(response && response.msg || '合并失败');
                showToast(response.msg || '合并成功', 'success');
                window.location.reload();
            }).catch(function (reason) {
                state.busy = false;
                invalidate();
                error((reason.message || '请求异常') + '；请核对列表，重新选择并预览后再操作。');
            });
    }
    function initialize() {
        if (state.initialized) return;
        state.initialized = true;
        node('mergeSearchBtn').addEventListener('click', function () { search(1); });
        node('mergeSearch').addEventListener('keydown', function (event) {
            if (event.key === 'Enter' && !event.isComposing) { event.preventDefault(); search(1); }
        });
        node('mergePrevBtn').addEventListener('click', function () { search(state.page - 1); });
        node('mergeNextBtn').addEventListener('click', function () { search(state.page + 1); });
        node('mergeHumanConfirmed').addEventListener('change', sync);
        node('mergeExecuteBtn').addEventListener('click', execute);
        node('mergeSwapBtn').addEventListener('click', function () {
            if (state.busy || !state.target) return;
            var previous = state.source; state.source = state.target; state.target = previous;
            node('mergeSearch').value = '';
            state.searchSeq += 1; search(1); preview();
        });
        node('materialMergeModal').addEventListener('hide.bs.modal', function (event) {
            if (state.busy) { event.preventDefault(); return; }
            state.searchSeq += 1; state.previewSeq += 1; state.preview = null;
        });
    }
    WMS.MaterialMerge = {open: function (source, target) {
        initialize();
        if (state.busy) return;
        state.source = source; state.target = target || null;
        state.page = 1; state.pages = 0; state.searchSeq += 1;
        node('mergeSearch').value = '';
        invalidate();
        bootstrap.Modal.getOrCreateInstance(node('materialMergeModal')).show();
        search(1);
        if (state.target) preview();
        node('mergeSearch').focus();
    }};
}());
