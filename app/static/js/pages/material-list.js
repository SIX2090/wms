const materialPageData = JSON.parse(document.getElementById('material-list-data').textContent);
const quickSelectData = materialPageData.relations;

const quickSelectTypeByHiddenId = {
    add_category_id: 'category',
    edit_category_id: 'category',
    add_unit_id: 'unit',
    edit_unit_id: 'unit',
    add_supplier_id: 'supplier',
    edit_supplier_id: 'supplier'
};

const quickSelectApiByType = {
    category: '/api/categories',
    unit: '/api/units',
    supplier: '/api/suppliers'
};

function normalizeQuickText(value) {
    return String(value || '').trim().toLowerCase();
}

function quickSelectLabel(item) {
    return item ? (item.name || item.code || '') : '';
}

function findQuickSelectItem(type, value) {
    const normalized = normalizeQuickText(value);
    if (!normalized) return null;
    return (quickSelectData[type] || []).find(function(item) {
        return normalizeQuickText(item.name) === normalized ||
               normalizeQuickText(item.code) === normalized ||
               String(item.id) === String(value);
    }) || null;
}

function filterQuickSelectItems(type, keyword) {
    const normalized = normalizeQuickText(keyword);
    const items = quickSelectData[type] || [];
    if (!normalized) return items.slice();
    return items.filter(function(item) {
        return normalizeQuickText(item.name).includes(normalized) ||
               normalizeQuickText(item.code).includes(normalized);
    });
}

function setQuickSelectValue(hiddenId, id) {
    const hidden = document.getElementById(hiddenId);
    const type = quickSelectTypeByHiddenId[hiddenId];
    if (!hidden || !type) return;
    const input = document.getElementById(hiddenId.replace('_id', '_input'));
    const item = id ? (quickSelectData[type] || []).find(function(row) { return String(row.id) === String(id); }) : null;
    hidden.value = item ? item.id : '';
    if (input) input.value = item ? quickSelectLabel(item) : '';
}

function closeQuickSelects(exceptRoot) {
    document.querySelectorAll('.quick-select.open').forEach(function(root) {
        if (root !== exceptRoot) root.classList.remove('open');
    });
}

function renderQuickSelectMenu(root, showAll) {
    const hidden = document.getElementById(root.dataset.hiddenId);
    const input = root.querySelector('.quick-select-input');
    const menu = root.querySelector('.quick-select-menu');
    const type = quickSelectTypeByHiddenId[root.dataset.hiddenId];
    if (!hidden || !input || !menu || !type) return;
    const matches = filterQuickSelectItems(type, showAll ? '' : input.value);
    if (!matches.length) {
        menu.innerHTML = '<div class="quick-select-empty">没有匹配项</div>';
    } else {
        menu.innerHTML = matches.map(function(item) {
            const active = String(item.id) === String(hidden.value) ? ' active' : '';
            const code = item.code ? '<span class="quick-code">' + escapeHtml(item.code) + '</span>' : '';
            return '<div class="quick-select-item' + active + '" data-id="' + item.id + '">' + escapeHtml(item.name) + code + '</div>';
        }).join('');
    }
    closeQuickSelects(root);
    root.classList.add('open');
    WMS.positionDropdown(input, menu, {minWidth: 220, maxHeight: 220});
}

function commitQuickSelectInput(root) {
    const hidden = document.getElementById(root.dataset.hiddenId);
    const input = root.querySelector('.quick-select-input');
    const type = quickSelectTypeByHiddenId[root.dataset.hiddenId];
    if (!hidden || !input || !type) return;
    const value = input.value.trim();
    if (!value) {
        hidden.value = '';
        return;
    }
    const item = findQuickSelectItem(type, value) || filterQuickSelectItems(type, value)[0] || null;
    if (item) {
        hidden.value = item.id;
        input.value = quickSelectLabel(item);
    } else {
        hidden.value = '';
    }
}

function commitQuickSelects(form) {
    if (!form) return;
    form.querySelectorAll('.quick-select').forEach(function(root) {
        commitQuickSelectInput(root);
        root.classList.remove('open');
    });
}



function initQuickSelects() {
    document.querySelectorAll('.quick-select').forEach(function(root) {
        if (root.dataset.ready === '1') return;
        root.dataset.ready = '1';
        const hidden = document.getElementById(root.dataset.hiddenId);
        const input = root.querySelector('.quick-select-input');
        const toggle = root.querySelector('.quick-select-toggle');
        const menu = root.querySelector('.quick-select-menu');
        if (!hidden || !input || !toggle || !menu) return;

        input.addEventListener('focus', function() { renderQuickSelectMenu(root, false); });
        input.addEventListener('input', function() {
            hidden.value = '';
            renderQuickSelectMenu(root, false);
        });
        input.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                root.classList.remove('open');
                return;
            }
            if (event.key === 'Enter') {
                event.preventDefault();
                const active = menu.querySelector('.quick-select-item.active') || menu.querySelector('.quick-select-item');
                if (active) setQuickSelectValue(root.dataset.hiddenId, active.dataset.id);
                else commitQuickSelectInput(root);
                root.classList.remove('open');
            }
        });
        input.addEventListener('blur', function() {
            setTimeout(function() {
                if (!root.contains(document.activeElement)) {
                    commitQuickSelectInput(root);
                    root.classList.remove('open');
                }
            }, 160);
        });
        toggle.addEventListener('click', function() {
            renderQuickSelectMenu(root, true);
            input.focus();
        });
        menu.addEventListener('mousedown', function(event) {
            const item = event.target.closest('.quick-select-item');
            if (!item) return;
            event.preventDefault();
            setQuickSelectValue(root.dataset.hiddenId, item.dataset.id);
            root.classList.remove('open');
        });
    });
}

function refreshQuickSelectData(types) {
    return Promise.all((types || Object.keys(quickSelectApiByType)).map(function(type) {
        return WMS.listCache.refresh(quickSelectData[type], quickSelectApiByType[type])
            .catch(function() { return false; });
    }));
}

window.WmsRefreshDropdowns = function() {
    refreshQuickSelectData();
};





function setInputValueIfExists(id, value) {
    var node = document.getElementById(id);
    if (node) node.value = value;
}

var materialDeleteBusy = false;

function getSelectedMaterialIds() {
    return Array.from(document.querySelectorAll('#materialTable .check-item:checked'), function(cb) {
        return cb.value;
    });
}

function getSelectedSingleId() {
    var ids = getSelectedMaterialIds();
    return ids.length === 1 ? ids[0] : null;
}

function updateToolbarButtons() {
    var count = getSelectedMaterialIds().length;
    var hasSelection = count > 0;
    var isSingleSelection = count === 1;
    document.getElementById('toolbarEditBtn').disabled = !isSingleSelection;
    document.getElementById('toolbarCopyBtn').disabled = !isSingleSelection;
    document.getElementById('toolbarPrintBtn').disabled = !hasSelection;
    const remotePrintButton = document.getElementById('toolbarRemotePrintBtn');
    remotePrintButton.disabled = !hasSelection || remotePrintButton.dataset?.runtimePaused === '1';
    document.getElementById('toolbarFindImageBtn').disabled = !isSingleSelection;
    document.getElementById('toolbarDeleteBtn').disabled = !hasSelection || materialDeleteBusy;
    document.getElementById('toolbarMergeBtn').disabled = count < 1 || count > 2;
}

function initToolbarActions() {
    var table = document.getElementById('materialTable');
    if (table) {
        table.addEventListener('change', function(e) {
            if (e.target.classList.contains('check-item') || e.target.id === 'checkAll') {
                updateToolbarButtons();
            }
        });
        // 初始化时更新一次
        updateToolbarButtons();
    }
}

function toolbarEdit() {
    var id = getSelectedSingleId();
    if (id) editMaterial(id);
}

function toolbarCopy() {
    var id = getSelectedSingleId();
    if (id) copyMaterial(id);
}

function toolbarPrint() {
    printLabels();
}

function sendLabelsToPrintStation() {
    var ids = getSelectedMaterialIds();
    if (!ids.length) {
        // 空选时给明确反馈：原来静默 return，用户会以为按钮失效。
        showToast('请先勾选要打印的物料', 'warning');
        return;
    }
    WMS.api.post('/print_queue/jobs', {job_type: 'label', target_ids: ids.join(',')})
    .then(function(res) {
        showToast(res.msg || '已发送标签到打印工作站', (res && res.duplicate) ? 'warning' : 'success');
    })
    .catch(function(err) {
        showToast('发送打印任务失败：' + err.message, 'danger');
    });
}

function toolbarFindImage() {
    var id = getSelectedSingleId();
    if (id) findMaterialImage(id);
}

// 列表缩略图点击放大预览
function previewMaterialImage(src) {
    if (!src) return;
    document.getElementById('imagePreviewImg').src = src;
    var modalEl = document.getElementById('imagePreviewModal');
    var modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.show();
}

function showMaterialDeleteResult(result) {
    var modalEl = document.getElementById('materialDeleteResultModal');
    var body = document.getElementById('materialDeleteResults');
    body.replaceChildren();
    document.getElementById('materialDeleteSummary').textContent = '已选 ' + result.selected_count + ' 条：已删除 ' +
        result.deleted_count + ' 条，保留 ' + result.skipped_count + ' 条，失败 ' + result.failed_count + ' 条。';
    var labels = {deleted: '已删除', skipped: '保留', failed: '失败，已保留'};
    (result.items || []).forEach(function(item) {
        var row = document.createElement('tr');
        [item.code || ('ID ' + item.id), item.name || '', labels[item.status] || '保留', item.reason || ''].forEach(function(value) {
            var cell = document.createElement('td');
            cell.textContent = value;
            row.appendChild(cell);
        });
        body.appendChild(row);
    });
    modalEl._deleteReload = result.deleted_count > 0;
    if (!modalEl._deleteResultBound) {
        modalEl.addEventListener('hidden.bs.modal', function() {
            if (modalEl._deleteReload) {
                modalEl._deleteReload = false;
                window.location.reload();
            }
        });
        modalEl._deleteResultBound = true;
    }
    (bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl)).show();
}

async function toolbarDelete() {
    if (materialDeleteBusy) return;
    var ids = getSelectedMaterialIds();
    if (!ids.length) {
        showToast('请先勾选要清理的物料', 'warning');
        return;
    }
    materialDeleteBusy = true;
    updateToolbarButtons();
    try {
        var confirmed = await showConfirm('确定清理已勾选的 ' + ids.length + ' 条物料吗？\n仅删除未使用、无库存且无引用的档案；已使用、有库存或图片的会自动保留。\n只处理本次勾选项，删除后不能在页面恢复。', {title: '删除未使用物料确认'});
        if (!confirmed) return;
        // Selection was captured before confirmation; never expand it to other pages or filters.
        var result = await WMS.api.post(materialPageData.urls.delete, {ids: ids});
        showMaterialDeleteResult(result);
    } catch (err) {
        var result = err && err.data && err.data.data;
        if (result && Array.isArray(result.items)) showMaterialDeleteResult(result);
        else showToast((err && err.message) || '物料清理失败，请稍后重试', 'danger');
    } finally {
        materialDeleteBusy = false;
        updateToolbarButtons();
    }
}

// 2026-09-25：物料停用 / 启用。停用只挡「新建单据时能否选到」，历史单据、
// 库存与报表不受影响——确认文案必须讲清这一点，否则用户不敢点。
function toggleMaterialStatus(id, status) {
    var label = status === 'inactive' ? '停用' : '启用';
    var tip = status === 'inactive'
        ? '停用后：新建单据不能再选到这个物料；\n已录入的历史单据、库存数量、台账与报表都不受影响。'
        : '启用后：新建单据可以重新选到这个物料。';
    if (!confirm('确定' + label + '这个物料吗？\n\n' + tip)) return;
    WMS.api.postRaw('/material/' + id + '/set_status', {status: status}).then(function (r) {
        if (r && r.status === 'success') {
            window.location.reload();
        } else {
            showToast((r && r.msg) || label + '失败', 'danger');
        }
    }).catch(function (e) {
        showToast(label + '失败：' + (e && e.message ? e.message : e), 'danger');
    });
}

// MATERIAL-MERGE-HUMAN-001：行按钮固定被合并方；工具栏支持选1或2条，再人工核对方向。
function mergeMaterialInto(id, sourceCode) {
    WMS.MaterialMerge.open({id: Number(id), code: sourceCode});
}
function toolbarMerge() {
    var selected = Array.from(document.querySelectorAll('#materialTable .check-item:checked')).map(function (node) {
        return {id: Number(node.value), code: node.closest('tr').querySelector('[data-column-key="code"]').textContent.trim()};
    });
    if (selected.length < 1 || selected.length > 2) return;
    WMS.MaterialMerge.open(selected[0], selected[1] || null);
}

// ==================== 列设置（显示/隐藏字段） ====================
var MATERIAL_COL_STORAGE_KEY = 'material_col_visibility_v1';
var MATERIAL_COL_DEFAULTS = [
    {key: 'code',     label: '物料编码'},
    {key: 'name',     label: '物料名称'},
    {key: 'brand',    label: '品牌'},
    {key: 'spec',     label: '规格'},
    {key: 'unit',     label: '单位'},
    {key: 'category', label: '分类'},
    {key: 'supplier', label: '供应商'},
    {key: 'purpose',  label: '用途'},
    {key: 'stock',    label: '库存'},
    {key: 'min_stock',label: '最低库存'},
    {key: 'price',    label: '单价'},
    {key: 'remark',   label: '备注'},
    {key: 'status',   label: '状态'},
    {key: 'image',    label: '图片'}
];

function loadMaterialColVisibility() {
    try {
        var saved = JSON.parse(localStorage.getItem(MATERIAL_COL_STORAGE_KEY) || 'null');
        if (Array.isArray(saved) && saved.length) return new Set(saved);
    } catch(e) {}
    return null;
}

function saveMaterialColVisibility(hiddenSet) {
    localStorage.setItem(MATERIAL_COL_STORAGE_KEY, JSON.stringify(Array.from(hiddenSet)));
}

function buildMaterialColOptions() {
    var container = document.getElementById('materialColOptions');
    if (!container) return;
    var hidden = loadMaterialColVisibility() || new Set();
    var html = '';
    MATERIAL_COL_DEFAULTS.forEach(function(col) {
        var checked = !hidden.has(col.key) ? ' checked' : '';
        html += '<div class="form-check material-col-option">' +
            '<input class="form-check-input" type="checkbox" id="matCol_' + col.key + '"' + checked + ' data-col-key="' + col.key + '">' +
            '<label class="form-check-label" for="matCol_' + col.key + '">' + col.label + '</label>' +
            '</div>';
    });
    container.innerHTML = html;

    container.querySelectorAll('.form-check-input').forEach(function(cb) {
        cb.addEventListener('change', function() {
            var key = this.dataset.colKey;
            var curHidden = loadMaterialColVisibility() || new Set();
            if (this.checked) {
                curHidden.delete(key);
            } else {
                curHidden.add(key);
            }
            saveMaterialColVisibility(curHidden);
            applyMaterialColVisibility(curHidden);
        });
    });
}

function applyMaterialColVisibility(hiddenSet) {
    var table = document.getElementById('materialTable');
    if (!table) return;
    hiddenSet = hiddenSet || loadMaterialColVisibility() || new Set();
    // 表头
    table.querySelectorAll('thead th[data-column-key]').forEach(function(th) {
        var key = th.dataset.columnKey;
        if (key === 'select') return;
        th.classList.toggle('cb-detail-hidden', hiddenSet.has(key));
    });
    // 表体
    table.querySelectorAll('tbody tr').forEach(function(tr) {
        tr.querySelectorAll('td[data-column-key]').forEach(function(td) {
            var key = td.dataset.columnKey;
            if (key === 'select') return;
            td.classList.toggle('cb-detail-hidden', hiddenSet.has(key));
        });
    });
}

function toggleMaterialColumnSettings() {
    var panel = document.getElementById('materialColSettingsPanel');
    if (!panel) return;
    var isOpen = panel.classList.contains('show');
    if (!isOpen) {
        buildMaterialColOptions();
    }
    panel.classList.toggle('show');
}

function resetMaterialColumns() {
    localStorage.removeItem(MATERIAL_COL_STORAGE_KEY);
    buildMaterialColOptions();
    applyMaterialColVisibility(new Set());
    showToast('列设置已重置', 'success', 1500);
}

// 点击面板外部关闭
document.addEventListener('click', function(e) {
    var panel = document.getElementById('materialColSettingsPanel');
    var btn = document.getElementById('toolbarColumnBtn');
    if (panel && !panel.contains(e.target) && btn && !btn.contains(e.target)) {
        panel.classList.remove('show');
    }
});

document.addEventListener('DOMContentLoaded', function() {
    initCheckAll('materialTable');
    initToolbarActions();
    applyMaterialColVisibility();
    if (typeof setupDynamicDetailColumnControls === 'function') {
        window.materialColumnController = setupDynamicDetailColumnControls({
            tableSelector: '#materialTable',
            orderKey: 'material_col_order_v1',
            widthKey: 'material_col_widths_v1',
            lockedColumns: ['select'],
            minWidths: {
                select: 50,
                code: 120,
                name: 140,
                spec: 100,
                unit: 70,
                category: 90,
                supplier: 110,
                purpose: 110,
                stock: 80,
                min_stock: 90,
                price: 80,
                remark: 160,
                image: 70
            }
        });
    }
    initQuickSelects();
    try {
        if (typeof BroadcastChannel !== 'undefined') {
            var masterBc = new BroadcastChannel('wms_master_data_update');
            masterBc.onmessage = function(event) {
                var type = event.data && event.data.type;
                if (type === 'unit_updated') refreshQuickSelectData(['unit']);
                if (type === 'supplier_updated') refreshQuickSelectData(['supplier']);
                if (type === 'category_updated') refreshQuickSelectData(['category']);
            };
        }
    } catch(e) {}

    var importForm = document.getElementById('importMaterialForm');
    if (importForm) {
        importForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var btn = document.getElementById('importBtn');
            var resultDiv = document.getElementById('importResult');
            btn.disabled = true;
            btn.textContent = '导入中...';
            resultDiv.style.display = 'none';
            resultDiv.innerHTML = '';
            var formData = new FormData(this);
            // The shared API preserves structured errors and non-JSON HTTP status.
            WMS.api.postRaw(this.action, formData)
            .then(function(res) {
                btn.disabled = false;
                btn.textContent = '导入';
                resultDiv.style.display = 'block';
                if (res && res.status === 'success') {
                    var html = '<div class="alert alert-success"><i class="bi bi-check-circle"></i> ' + escapeHtml(res.msg) + '</div>';
                    if (res.warnings) {
                        html += '<div class="alert alert-warning"><i class="bi bi-exclamation-triangle"></i> ' + escapeHtml(res.warnings) + '</div>';
                    }
                    resultDiv.innerHTML = html;
                    setTimeout(function() { location.reload(); }, 2000);
                } else {
                    var errMsg = (res && res.msg) ? res.msg : '未知错误';
                    resultDiv.innerHTML = '<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ' + escapeHtml(errMsg) + '</div>';
                }
            })
            .catch(function(err) {
                btn.disabled = false;
                btn.textContent = '导入';
                resultDiv.style.display = 'block';
                var msg = (err && err.message) ? err.message : '请求失败，请稍后重试';
                resultDiv.innerHTML = '<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ' + escapeHtml(msg) + '</div>';
            });
        });
    }

    // 每页显示条数切换
    var perPageSelect = document.getElementById('perPageSelect');
    if (perPageSelect) {
        perPageSelect.addEventListener('change', function() {
            var perPage = this.value;
            var currentUrl = new URL(window.location.href);
            currentUrl.searchParams.set('per_page', perPage);
            currentUrl.searchParams.set('page', '1');
            window.location.href = currentUrl.toString();
        });
    }

    // 表头排序点击处理
    var sortableHeaders = document.querySelectorAll('.sortable-header');
    sortableHeaders.forEach(function(th) {
        th.addEventListener('click', function(e) {
            if (e.target.closest('.col-resize')) return;
            // 如果正在拖拽，不触发排序
            if (this.dataset.dragging === 'true') return;
            var sortField = this.dataset.sortable;
            if (!sortField) return;
            var currentSort = materialPageData.sortBy;
            var currentOrder = materialPageData.sortOrder;
            var newOrder = (currentSort === sortField && currentOrder === 'asc') ? 'desc' : 'asc';
            var url = new URL(window.location.href);
            url.searchParams.set('sort', sortField);
            url.searchParams.set('order', newOrder);
            url.searchParams.set('page', '1');
            window.location.href = url.toString();
        });
    });

    document.getElementById('addModal').addEventListener('show.bs.modal', function() {
        window.WmsRefreshDropdowns && window.WmsRefreshDropdowns();
    });
    document.getElementById('editModal').addEventListener('show.bs.modal', function() {
        window.WmsRefreshDropdowns && window.WmsRefreshDropdowns();
    });

    // 新增物料
    var addForm = document.getElementById('addForm');
    if (addForm) {
        document.getElementById('addModal').addEventListener('hidden.bs.modal', function() {
            addForm.reset();
            setWmsDateInputValue(document.getElementById('add_expiry_date'), '');
            ['add_category_id', 'add_unit_id', 'add_supplier_id'].forEach(function(id) { setQuickSelectValue(id, ''); });
            document.getElementById('addModalTitle').textContent = '新增物料';
            document.getElementById('copyHint').classList.add('d-none');
        });

        addForm.addEventListener('submit', function(e) {
            e.preventDefault();
            commitQuickSelects(this);
            var formData = new FormData(this);
            WMS.api.postRaw(materialPageData.urls.add, formData)
            .then(function(res) {
                if (res.status === 'success') {
                    // 广播通知其他页面刷新物料列表
                    try {
                        if (typeof BroadcastChannel !== 'undefined') {
                            var bc = new BroadcastChannel('wms_material_update');
                            bc.postMessage({type: 'material_updated', timestamp: Date.now()});
                            bc.close();
                        }
                    } catch(e) {}
                    showToast(res.msg || '物料保存成功，正在刷新列表…', 'success', 1800);
                    setTimeout(function(){ location.reload(); }, 500);
                }
                else showToast(res.msg || '保存失败', 'danger', 3600);
            })
            .catch(function(err){ showToast('保存失败：' + err.message, 'danger', 3600); });
        });
    }

    // 编辑物料 - 打开编辑弹窗
    window.editMaterial = function(id) {
        return loadWmsMasterEditor('material', id, function(mat) {
            document.getElementById('edit_id').value = mat.id;
            document.getElementById('edit_code').value = mat.code;
            document.getElementById('edit_code').setAttribute('data-original', mat.code);
            document.getElementById('edit_name').value = mat.name;
            document.getElementById('edit_name').setAttribute('data-original', mat.name);
            setQuickSelectValue('edit_category_id', mat.category_id || '');
            setQuickSelectValue('edit_unit_id', mat.unit_id || '');
            setQuickSelectValue('edit_supplier_id', mat.supplier_id || '');
            document.getElementById('edit_spec').value = mat.spec || '';
            document.getElementById('edit_brand').value = mat.brand || '';
            document.getElementById('edit_purpose').value = mat.purpose || '';
            document.getElementById('edit_price').value = mat.price || 0;
            setInputValueIfExists('edit_min_stock', mat.min_stock || 0);
            setInputValueIfExists('edit_max_stock', mat.max_stock || 0);
            setInputValueIfExists('edit_reorder_point', mat.reorder_point || 0);
            setWmsDateInputValue(document.getElementById('edit_expiry_date'), mat.expiry_date || '');
            setInputValueIfExists('edit_alert_days', mat.alert_days || 30);
            setInputValueIfExists('edit_remark', mat.remark || '');
            var imageInput = document.getElementById('edit_image_upload');
            if (imageInput) imageInput.value = '';

            // 统一多图：加载物料档案图片（手机/电脑共用 MaterialImage 表）
            loadEditMaterialImages(mat.id);

            // 显示编辑弹窗
            var editModal = new bootstrap.Modal(document.getElementById('editModal'));
            editModal.show();
        });
    };

    window.getEditMaterialContext = function(id) {
        var modal = document.getElementById('editModal');
        var input = document.getElementById('edit_id');
        var state = modal && modal._wmsMasterEditor;
        var version = state && state.version;
        function current() {
            return !!(state && !state.pending && state.recordId === String(id) && state.version === version &&
                modal._wmsMasterEditor === state && modal.isConnected && input && input.isConnected &&
                document.getElementById('editModal') === modal && document.getElementById('edit_id') === input &&
                String(input.value) === String(id));
        }
        return current() ? { isCurrent: current } : null;
    };

    // 编辑物料 - 加载物料档案图片（手机/电脑统一的多图）
    window.loadEditMaterialImages = function(id) {
        var context = getEditMaterialContext(id);
        var grid = document.getElementById('editMaterialImageGrid');
        if (!context || !grid || !grid.isConnected) return;
        var version = (loadEditMaterialImages.version || 0) + 1;
        loadEditMaterialImages.version = version;
        function current() {
            return context.isCurrent() && loadEditMaterialImages.version === version && grid.isConnected &&
                document.getElementById('editMaterialImageGrid') === grid;
        }
        grid.textContent = '图片加载中…';
        return WMS.api.getRaw('/mobile/api/material_archive/' + id + '/images')
            .then(function(res) {
                if (!current()) return;
                if (!res || res.status !== 'success') {
                    grid.innerHTML = '<div class="text-muted small">图片加载失败</div>';
                    return;
                }
                var images = (res.data && res.data.images) || [];
                if (!Array.isArray(images)) throw new Error('返回的图片数据无效，请重试');
                if (!images.length) {
                    grid.innerHTML = '<div class="text-muted small">暂无图片</div>';
                    return;
                }
                var html = '';
                images.forEach(function(img) {
                    html += '<div class="material-image-card">'
                        + '<img src="' + (img.url || img.image) + '" alt="物料图片">'
                        + '<div class="image-meta">'
                        + '<button type="button" class="btn btn-sm btn-outline-danger" data-material-action="deleteEditMaterialImage" data-material-id="' + img.id + '">删除</button>'
                        + '</div>'
                        + '</div>';
                });
                grid.innerHTML = html;
            })
            .catch(function(err){
                if (current()) grid.textContent = '图片加载失败：' + err.message;
            });
    };

    // 编辑物料 - 删除一张档案图片
    window.deleteEditMaterialImage = function(imageId) {
        if (isWmsMasterEditPending()) return;
        if (!confirm('确定删除这张物料图片吗？')) return;
        var editId = document.getElementById('edit_id').value;
        var context = getEditMaterialContext(editId);
        if (!context) return;
        WMS.api.delete('/mobile/api/material_archive/images/' + imageId)
            .then(function(res) {
                if (!context.isCurrent()) return;
                showToast('图片已删除', 'success', 2000);
                loadEditMaterialImages(editId);
            })
            .catch(function(err){ if (context.isCurrent()) showToast((err && (err.msg || err.message)) || '删除失败', 'danger', 3600); });
    };

    // 编辑物料 - 上传一张档案图片（即时上传，调用移动端统一 upload 接口）
    window.uploadEditMaterialImage = function(input) {
        if (!input || !input.files || !input.files.length) return;
        if (isWmsMasterEditPending()) return;
        var editId = document.getElementById('edit_id').value;
        if (!editId) { showToast('请先选择要编辑的物料', 'danger'); input.value = ''; return; }
        var context = getEditMaterialContext(editId);
        if (!context) return;
        var file = input.files[0];
        var formData = new FormData();
        formData.append('image', file);
        showToast('正在上传图片...', 'info', 1500);
        WMS.api.post('/mobile/api/material_archive/' + editId + '/images', formData)
            .then(function() {
                if (!context.isCurrent()) return;
                showToast('图片已上传', 'success', 2000);
                input.value = '';
                loadEditMaterialImages(editId);
            })
            .catch(function(err){ if (context.isCurrent()) { showToast((err && (err.msg || err.message)) || '上传失败', 'danger', 3600); input.value = ''; } });
    };

    window.copyMaterial = function(id) {
        WMS.api.post('/material/' + id + '/copy')
            .then(function(res) {
                var mat = res.material;
                var modalEl = document.getElementById('addModal');
                    var modal = bootstrap.Modal.getInstance(modalEl);
                    if (!modal) {
                        modal = new bootstrap.Modal(modalEl);
                    }
                    modal.hide();
                    setTimeout(function() {
                        addForm.reset();
                        document.getElementById('addModalTitle').textContent = '复制物料（编辑状态）';
                        document.getElementById('copyHint').classList.remove('d-none');
                        document.getElementById('add_code').value = mat.suggested_code || '';
                        document.getElementById('add_code').placeholder = '系统已自动生成编号';
                        document.getElementById('add_name').value = mat.name || '';
                        setQuickSelectValue('add_category_id', mat.category_id || '');
                        setQuickSelectValue('add_unit_id', mat.unit_id || '');
                        setQuickSelectValue('add_supplier_id', mat.supplier_id || '');
                        document.getElementById('add_spec').value = mat.spec || '';
                        document.getElementById('add_brand').value = mat.brand || '';
                        document.getElementById('add_purpose').value = mat.purpose || '';
                        document.getElementById('add_price').value = mat.price || 0;
                        setInputValueIfExists('add_min_stock', mat.min_stock || 0);
                        setInputValueIfExists('add_max_stock', mat.max_stock || 0);
                        setInputValueIfExists('add_reorder_point', mat.reorder_point || 0);
                        setInputValueIfExists('add_alert_days', mat.alert_days || 30);
                        setWmsDateInputValue(document.getElementById('add_expiry_date'), mat.expiry_date || '');
                        setInputValueIfExists('add_remark', mat.remark || '');
                        modal.show();
                    }, 150);
            })
            .catch(function(err){ showToast((err && (err.msg || err.message)) || '复制失败', 'danger', 3600); });
    };

    var materialImageRequestGeneration = 0;
    var materialImageContext = null;

    function materialImageDomIsCurrent(context) {
        return materialImageContext === context && context.generation === materialImageRequestGeneration
            && context.modalEl.isConnected && context.statusEl.isConnected
            && context.gridEl.isConnected && context.queryEl.isConnected
            && document.getElementById('materialImageModal') === context.modalEl
            && document.getElementById('materialImageStatus') === context.statusEl
            && document.getElementById('materialImageGrid') === context.gridEl
            && document.getElementById('materialImageQuery') === context.queryEl
            && context.modalEl.dataset.materialImageId === context.materialId;
    }

    function materialImageIsCurrent(context) {
        return context.active && materialImageDomIsCurrent(context);
    }

    window.findMaterialImage = function(id) {
        var modalEl = document.getElementById('materialImageModal');
        var statusEl = document.getElementById('materialImageStatus');
        var gridEl = document.getElementById('materialImageGrid');
        var queryEl = document.getElementById('materialImageQuery');
        if (!modalEl || !statusEl || !gridEl || !queryEl) return;
        var modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
        var context = {
            generation: ++materialImageRequestGeneration, materialId: String(id),
            modalEl: modalEl, statusEl: statusEl, gridEl: gridEl, queryEl: queryEl,
            active: true, saving: false, completed: false, buttons: []
        };
        materialImageContext = context;
        modalEl.dataset.materialImageId = context.materialId;
        if (!modalEl._materialImageLifecycleBound) {
            modalEl._materialImageLifecycleBound = true;
            ['hide.bs.modal', 'hidden.bs.modal'].forEach(function(eventName) {
                modalEl.addEventListener(eventName, function() {
                    if (materialImageContext && materialImageContext.modalEl === modalEl) {
                        materialImageContext.active = false;
                    }
                });
            });
        }
        statusEl.textContent = '正在搜索候选图片...';
        statusEl.className = 'text-muted py-3';
        gridEl.innerHTML = '';
        queryEl.textContent = '';
        modal.show();

        WMS.api.getRaw('/material/' + id + '/image_candidates')
            .then(function(res) {
                if (!materialImageIsCurrent(context)) return;
                if (res.status !== 'success') {
                    statusEl.textContent = res.msg || '找图失败';
                    statusEl.className = 'text-danger py-3';
                    return;
                }
                queryEl.textContent = res.query ? ('搜索词：' + res.query) : '';
                var candidates = res.candidates || [];
                if (!candidates.length) {
                    statusEl.textContent = '没有找到可用候选图，请尝试补充规格/品牌，或手动上传图片。';
                    statusEl.className = 'text-muted py-3';
                    return;
                }
                statusEl.textContent = '请选择一张确认绑定。';
                statusEl.className = 'text-muted pb-3';
                candidates.forEach(function(candidate) {
                    var card = document.createElement('div');
                    card.className = 'material-image-card';
                    var img = document.createElement('img');
                    img.src = candidate.thumb_url || candidate.image_url;
                    img.alt = candidate.title || '候选图片';
                    img.referrerPolicy = 'no-referrer';
                    img.onerror = function() {
                        this.src = candidate.image_url;
                    };
                    var meta = document.createElement('div');
                    meta.className = 'image-meta';
                    var title = document.createElement('div');
                    title.className = 'image-title';
                    title.textContent = candidate.title || candidate.source_url || '候选图片';
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'btn btn-sm btn-primary mt-2';
                    btn.innerHTML = '<i class="bi bi-check2"></i> 选用';
                    context.buttons.push(btn);
                    btn.addEventListener('click', function() {
                        if (!materialImageIsCurrent(context) || !btn.isConnected || context.saving || context.completed) return;
                        context.saving = true;
                        context.buttons.forEach(function(button) { button.disabled = true; });
                        btn.textContent = '保存中...';
                        WMS.api.postRaw('/material/' + id + '/image_select', {image_url: candidate.image_url})
                        .then(function(saveRes) {
                            if (!materialImageIsCurrent(context) || !btn.isConnected) return;
                            if (saveRes.status === 'success') {
                                context.completed = true;
                                showToast('图片已保存', 'success', 2200);
                                modal.hide();
                                setTimeout(function() {
                                    if (context.completed && materialImageDomIsCurrent(context)) location.reload();
                                }, 300);
                            } else {
                                context.saving = false;
                                context.buttons.forEach(function(button) { button.disabled = false; });
                                btn.innerHTML = '<i class="bi bi-check2"></i> 选用';
                                showToast(saveRes.msg || '保存失败', 'danger', 3600);
                            }
                        })
                        .catch(function(err) {
                            if (!materialImageIsCurrent(context) || !btn.isConnected) return;
                            context.saving = false;
                            context.buttons.forEach(function(button) { button.disabled = false; });
                            btn.innerHTML = '<i class="bi bi-check2"></i> 选用';
                            showToast('保存失败：' + err.message, 'danger', 3600);
                        });
                    });
                    meta.appendChild(title);
                    meta.appendChild(btn);
                    card.appendChild(img);
                    card.appendChild(meta);
                    gridEl.appendChild(card);
                });
            })
            .catch(function(err) {
                if (!materialImageIsCurrent(context)) return;
                statusEl.textContent = '找图失败：' + err.message;
                statusEl.className = 'text-danger py-3';
            });
    };

    // 修复空分类/单位
    window.fixEmptyFields = function() {
        if (!confirm('将把所有空分类设为"默认分类"，空单位设为"个"，确定修复吗？')) return;
        WMS.api.postRaw(materialPageData.urls.fix, {})
        .then(function(res) {
            showToast(res.msg || '修复完成', res.status === 'success' ? 'success' : 'danger');
            if (res.status === 'success') location.reload();
        })
        .catch(function(err){ showToast('修复失败: ' + err.message, 'danger'); });
    };

    // 删除全部物料入口已禁用，后端也会拒绝请求。
    window.deleteAllMaterials = function() {
        showToast('线上系统已禁用删除全部物料，请走停机维护流程', 'warning');
    };

    // 编辑物料 - 提交表单
    var editForm = document.getElementById('editForm');
    if (editForm) {
        editForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (isWmsMasterEditPending()) return;
            commitQuickSelects(this);
            var formData = new FormData(this);
            var id = document.getElementById('edit_id').value;
            var originalCode = document.getElementById('edit_code').getAttribute('data-original');
            var currentCode = document.getElementById('edit_code').value.trim();
            var originalName = document.getElementById('edit_name').getAttribute('data-original');
            var currentName = document.getElementById('edit_name').value.trim();

            function doSubmit() {
                // 立即关闭确认对话框的 overlay
                var confirmOverlay = document.getElementById('cbConfirmOverlay');
                if (confirmOverlay) {
                    confirmOverlay.classList.remove('show');
                }

                WMS.api.postRaw('/material/edit/' + id, formData)
                .then(function(res) {
                    if (res.status === 'success') {
                        // 先关闭编辑弹窗
                        var editModalEl = document.getElementById('editModal');
                        var editModalInstance = bootstrap.Modal.getInstance(editModalEl);
                        if (editModalInstance) {
                            editModalInstance.hide();
                        }

                        // 广播通知其他页面刷新物料列表
                        try {
                            if (typeof BroadcastChannel !== 'undefined') {
                                var bc = new BroadcastChannel('wms_material_update');
                                bc.postMessage({type: 'material_updated', timestamp: Date.now()});
                                bc.close();
                            }
                        } catch(e) {}

                        // 等待模态框完全关闭后再重新加载页面
                        setTimeout(function() {
                            if (res.msg && res.msg !== '物料更新成功') {
                                showToast(res.msg, 'success', 4000);
                                setTimeout(function(){ location.reload(); }, 1200);
                            } else {
                                location.reload();
                            }
                        }, 300);
                    } else {
                        showToast(res.msg || '保存失败', 'danger', 3600);
                    }
                })
                .catch(function(err){ showToast('保存失败：' + err.message, 'danger', 3600); });
            }

            // 直接提交，不再弹出确认对话框
            doSubmit();
        });
    }
});

// 标签打印模板相关函数
var labelTemplateModal;
var selectedCell = null;
var selectedCells = [];  // 多选单元格集合（Ctrl+点击切换），含主选中 selectedCell
var currentTemplateId = null;  // 当前载入编辑的模板ID（null=未载入，保存走新建）
var labelTemplateGeneration = 0;
var labelTemplateLoading = false;
var labelTemplateLoadFailed = false;
var labelTemplateWriteBusy = false;

function __labelTemplateStatus(message) {
    var status = document.getElementById('labelTemplateStatus');
    if (status) status.textContent = message;
}

function __invalidateTemplateLoad() {
    if (labelTemplateLoading) {
        document.getElementById('templateSelect').value = '';
        document.getElementById('templateNameInput').value = '';
        currentTemplateId = null;
        __labelTemplateStatus('当前画布作为新设计，保存时新建模板');
    }
    labelTemplateGeneration++;
    labelTemplateLoading = false;
    labelTemplateLoadFailed = false;
}

function __canWriteLabelTemplate() {
    if (labelTemplateWriteBusy) return false;
    if (labelTemplateLoading || labelTemplateLoadFailed) {
        __notify('请先成功加载模板，或清空后新建设计', 'warning');
        return false;
    }
    return true;
}

function __runLabelTemplateWrite(action) {
    if (!__canWriteLabelTemplate()) return;
    labelTemplateWriteBusy = true;
    var controls = [];
    var modal = document.getElementById('labelTemplateModal');
    if (modal) modal.querySelectorAll('button, input, select, textarea, [contenteditable]').forEach(function(el) {
        controls.push({el: el, disabled: el.disabled, editable: el.getAttribute('contenteditable')});
        if ('disabled' in el) el.disabled = true;
        if (el.hasAttribute('contenteditable')) el.setAttribute('contenteditable', 'false');
    });
    return Promise.resolve().then(action).catch(function(err) {
        __notify((err && err.message) || '模板操作失败，请稍后重试', 'danger');
    }).finally(function() {
        labelTemplateWriteBusy = false;
        controls.forEach(function(item) {
            if ('disabled' in item.el) item.el.disabled = item.disabled;
            if (item.editable !== null) item.el.setAttribute('contenteditable', item.editable);
        });
    });
}

function __requireTemplateSuccess(res) {
    if (!res || res.status !== 'success') throw new Error((res && res.msg) || '模板操作失败：服务器响应无效');
    return res;
}

var __labelDesignerModal = document.getElementById('labelTemplateModal');
if (__labelDesignerModal) __labelDesignerModal.addEventListener('hide.bs.modal', function(event) {
    if (labelTemplateWriteBusy) { event.preventDefault(); return; }
    __invalidateTemplateLoad();
});
// 撤销/重做历史栈（快照基于 cells 布局，恢复走 loadTemplateToEditor）
var __undoStack = [];
var __redoStack = [];
var __lastSnap = null;
var __lastPushTime = 0;
var __applyingHistory = false;
var currentTemplate = {
    rows: 3,
    cols: 2,
    cells: [],
    labelWidth: 60,
    labelHeight: 40
};

// BUG-2026-09-08-001：按 DOM 实际顺序重排所有单元格的 data-row/data-col。
// 删除行/列后残留的过期坐标若被直接序列化，打印端按声明 rows×cols 网格
// 迭代会把越界单元格静默丢弃（字段打印不出来）。保存/草稿前统一重排，
// 保证存下去的坐标永远等于用户当前所见布局。
function reindexLabelCells() {
    var table = document.getElementById('labelTable');
    if (!table) return;
    for (var r = 0; r < table.rows.length; r++) {
        var row = table.rows[r];
        var colPos = 0;
        for (var i = 0; i < row.cells.length; i++) {
            var cell = row.cells[i];
            if (!cell.classList || !cell.classList.contains('label-cell')) {
                colPos += cell.colSpan || 1;
                continue;
            }
            cell.dataset.row = r;
            cell.dataset.col = colPos;
            colPos += cell.colSpan || 1;
        }
    }
}

// ==================== 撤销/重做 + 多选 + 快捷键（标签设计器可用性增强） ====================

function __captureSnapshot() {
    reindexLabelCells();
    var cells = [];
    document.querySelectorAll('#labelTable .label-cell').forEach(function(cell) {
        var content = cell.querySelector('.cell-content');
        if (!content) return;
        var cellData = {
            row: cell.dataset.row, col: cell.dataset.col,
            text: content.textContent, field: content.dataset.field || '',
            style: {
                fontSize: content.style.fontSize, fontWeight: content.style.fontWeight,
                color: content.style.color, textAlign: content.style.textAlign,
                verticalAlign: content.style.verticalAlign || cell.style.verticalAlign || ''
            },
            colSpan: cell.colSpan
        };
        if (content.dataset.field === 'barcode' || content.dataset.field === 'qrcode') {
            cellData.barcodeWidth = content.dataset.barcodeWidth || (content.dataset.field === 'qrcode' ? '25' : '50');
            cellData.barcodeHeight = content.dataset.barcodeHeight || (content.dataset.field === 'qrcode' ? '25' : '15');
        }
        cells.push(cellData);
    });
    var rowHeights = [];
    var table = document.getElementById('labelTable');
    for (var i = 0; i < table.rows.length; i++) {
        rowHeights.push(parseInt(table.rows[i].style.height) || 30);
    }
    return {
        rows: currentTemplate.rows, cols: currentTemplate.cols,
        labelWidth: currentTemplate.labelWidth, labelHeight: currentTemplate.labelHeight,
        cells: cells, rowHeights: rowHeights
    };
}

function __pushUndo() {
    var snap = __captureSnapshot();
    var now = Date.now();
    if (__lastSnap && JSON.stringify(__lastSnap) !== JSON.stringify(snap)) {
        // 800ms 内的连续变更（如文本逐字输入）合并为一个撤销点
        if (now - __lastPushTime > 800) {
            __undoStack.push(__lastSnap);
            if (__undoStack.length > 50) __undoStack.shift();
            __redoStack = [];
            __lastPushTime = now;
        }
    }
    __lastSnap = snap;
}

function __resetHistory() {
    __undoStack = [];
    __redoStack = [];
    __lastSnap = null;
    __lastPushTime = 0;
    __pushUndo();  // 记录初始快照
}

function __afterHistoryApply() {
    selectedCells = [];
    selectedCell = null;
    document.getElementById('cellProperties').style.display = 'none';
    document.getElementById('noSelection').style.display = 'block';
    document.querySelectorAll('.label-cell').forEach(function(c) { c.classList.remove('selected'); });
}

function undoTemplate() {
    if (labelTemplateWriteBusy) return;
    __invalidateTemplateLoad();
    if (!__undoStack.length) return;
    __redoStack.push(__lastSnap);
    __lastSnap = __undoStack.pop();
    __applyingHistory = true;
    loadTemplateToEditor(__lastSnap);
    __applyingHistory = false;
    __afterHistoryApply();
}

function redoTemplate() {
    if (labelTemplateWriteBusy) return;
    __invalidateTemplateLoad();
    if (!__redoStack.length) return;
    __undoStack.push(__lastSnap);
    __lastSnap = __redoStack.pop();
    __applyingHistory = true;
    loadTemplateToEditor(__lastSnap);
    __applyingHistory = false;
    __afterHistoryApply();
}

function __getTargetCells() {
    if (selectedCells && selectedCells.length) return selectedCells;
    return selectedCell ? [selectedCell] : [];
}

function clearSelectedCells() {
    if (labelTemplateWriteBusy) return;
    var cells = __getTargetCells();
    if (!cells.length) { __notify('请先点击选中单元格（Ctrl+点击可多选）', 'warning'); return; }
    cells.forEach(function(cell) {
        var content = cell.querySelector('.cell-content');
        if (content) {
            content.textContent = '';
            content.dataset.field = '';
            delete content.dataset.barcodeWidth;
            delete content.dataset.barcodeHeight;
        }
    });
    saveTemplateToStorage();
    __refreshCellDraggable();
}

// 字段搜索：按名称/标签/字段名过滤左侧字段
(function() {
    var input = document.getElementById('fieldSearchInput');
    if (!input) return;
    input.addEventListener('input', function() {
        var q = this.value.trim().toLowerCase();
        document.querySelectorAll('.field-item').forEach(function(item) {
            var text = (item.textContent + ' ' + (item.dataset.label || '') + ' ' + (item.dataset.field || '')).toLowerCase();
            item.style.display = (!q || text.indexOf(q) >= 0) ? '' : 'none';
        });
    });
})();

// 快捷键：Ctrl+Z 撤销 / Ctrl+Y 或 Ctrl+Shift+Z 重做 / Delete 清空选中（文本编辑时不劫持）
document.addEventListener('keydown', function(e) {
    var modal = document.getElementById('labelTemplateModal');
    if (!modal || !modal.classList.contains('show')) return;
    var ae = document.activeElement;
    var editing = ae && (ae.isContentEditable || ae.tagName === 'INPUT' || ae.tagName === 'SELECT' || ae.tagName === 'TEXTAREA');
    var key = e.key;
    if ((e.ctrlKey || e.metaKey) && !editing && (key === 'z' || key === 'Z')) {
        e.preventDefault();
        if (e.shiftKey) { redoTemplate(); } else { undoTemplate(); }
    } else if ((e.ctrlKey || e.metaKey) && !editing && (key === 'y' || key === 'Y')) {
        e.preventDefault();
        redoTemplate();
    } else if (!editing && (key === 'Delete' || key === 'Backspace') && __getTargetCells().length) {
        e.preventDefault();
        clearSelectedCells();
    }
});

// 将当前编辑器状态自动保存为草稿（localStorage），防止误关闭丢失未保存的设计
function saveTemplateToStorage() {
    if (labelTemplateLoading && !labelTemplateWriteBusy) __invalidateTemplateLoad();
    try {
        var table = document.getElementById('labelTable');
        if (!table) return;
        __pushUndo();
        reindexLabelCells();
        var cells = [];
        table.querySelectorAll('.label-cell').forEach(function(cell) {
            var content = cell.querySelector('.cell-content');
            if (!content) return;
            var cellData = {
                row: cell.dataset.row,
                col: cell.dataset.col,
                text: content.textContent,
                field: content.dataset.field || '',
                style: {
                    fontSize: content.style.fontSize,
                    fontWeight: content.style.fontWeight,
                    color: content.style.color,
                    textAlign: content.style.textAlign,
                    verticalAlign: content.style.verticalAlign || cell.style.verticalAlign || ''
                },
                colSpan: cell.colSpan
            };
            if (content.dataset.field === 'barcode' || content.dataset.field === 'qrcode') {
                cellData.barcodeWidth = content.dataset.barcodeWidth || (content.dataset.field === 'qrcode' ? '25' : '50');
                cellData.barcodeHeight = content.dataset.barcodeHeight || (content.dataset.field === 'qrcode' ? '25' : '15');
            }
            cells.push(cellData);
        });
        var rowHeights = [];
        for (var i = 0; i < table.rows.length; i++) {
            rowHeights.push(parseInt(table.rows[i].style.height) || 30);
        }
        var draft = {
            rows: currentTemplate.rows,
            cols: currentTemplate.cols,
            labelWidth: currentTemplate.labelWidth,
            labelHeight: currentTemplate.labelHeight,
            cells: cells,
            rowHeights: rowHeights
        };
        localStorage.setItem('labelTemplateDraft', JSON.stringify(draft));
    } catch (e) {
        console.warn('标签模板草稿保存失败:', e);
    }
}

// 无任何已保存模板时，恢复上次未保存的草稿
function restoreTemplateDraft(afterWrite) {
    if (labelTemplateWriteBusy && !afterWrite) return;
    __invalidateTemplateLoad();
    currentTemplateId = null;
    document.getElementById('templateSelect').value = '';
    document.getElementById('templateNameInput').value = '';
    try {
        var raw = localStorage.getItem('labelTemplateDraft');
        if (!raw) return;
        var draft = JSON.parse(raw);
        if (draft && draft.cells && draft.cells.length > 0) {
            loadTemplateToEditor(draft);
        }
    } catch (e) {
        console.warn('标签模板草稿恢复失败:', e);
    }
}

function openLabelTemplate() {
    if (labelTemplateWriteBusy) return;
    labelTemplateModal = new bootstrap.Modal(document.getElementById('labelTemplateModal'));
    labelTemplateModal.show();

    // 重置选中状态
    selectedCell = null;
    selectedCells = [];
    document.getElementById('cellProperties').style.display = 'none';
    document.getElementById('noSelection').style.display = 'block';
    document.querySelectorAll('.label-cell').forEach(c => c.classList.remove('selected'));

    // 重置委托标志，确保每次打开都能正确绑定事件
    var table = document.getElementById('labelTable');
    if (table) table._dragDelegated = false;

    // 加载模板列表
    loadTemplateList();

    initTemplateDragDrop();
    // 同步画布物理尺寸与缩放占位（AA5）
    updateCanvasSize();
}

// ==================== 画布内拖动字段 + 双击插入（标签设计器可用性增强 AA4） ====================
var __cellDragSrc = null;  // 画布内被拖拽的源单元格（区别于从字段面板拖入）

function __ensureCellContent(cell) {
    var content = cell.querySelector('.cell-content');
    if (!content) {
        cell.innerHTML = '<span class="cell-content" contenteditable="true" style="display: block; font-size: 12px; overflow: hidden; white-space: normal; word-break: break-all;"></span>';
        content = cell.querySelector('.cell-content');
    }
    return content;
}

// 读取/写入单元格的可移动数据（不含 colSpan，避免破坏网格结构）
function __cellData(cell) {
    var c = cell.querySelector('.cell-content');
    return {
        text: c ? c.textContent : '',
        field: c ? (c.dataset.field || '') : '',
        bw: c ? (c.dataset.barcodeWidth || '') : '',
        bh: c ? (c.dataset.barcodeHeight || '') : '',
        fontSize: c ? c.style.fontSize : '',
        fontWeight: c ? c.style.fontWeight : '',
        color: c ? c.style.color : '',
        textAlign: c ? c.style.textAlign : '',
        verticalAlign: cell.style.verticalAlign || ''
    };
}

function __applyCellData(cell, d) {
    var c = __ensureCellContent(cell);
    c.textContent = d.text;
    c.dataset.field = d.field;
    if (d.bw) { c.dataset.barcodeWidth = d.bw; } else { delete c.dataset.barcodeWidth; }
    if (d.bh) { c.dataset.barcodeHeight = d.bh; } else { delete c.dataset.barcodeHeight; }
    c.style.fontSize = d.fontSize || '12px';
    c.style.fontWeight = d.fontWeight || 'normal';
    c.style.color = d.color || '#000000';
    c.style.textAlign = d.textAlign || 'left';
    cell.style.verticalAlign = d.verticalAlign || '';
}

function __swapCells(a, b) {
    var da = __cellData(a);
    var db = __cellData(b);
    __applyCellData(a, db);
    __applyCellData(b, da);
}

function __cellHasContent(cell) {
    var c = cell.querySelector('.cell-content');
    return !!(c && (c.dataset.field || c.textContent.trim()));
}

// 让有内容的单元格可拖拽（编辑时临时禁用，避免与文本光标冲突）
function __refreshCellDraggable() {
    document.querySelectorAll('#labelTable .label-cell').forEach(function(cell) {
        var editing = document.activeElement && cell.contains(document.activeElement);
        cell.draggable = __cellHasContent(cell) && !editing;
    });
}

// 双击字段：插入到当前选中格（无选中则第一个空格）
function insertFieldToSelection(field, label) {
    var target = selectedCell;
    if (!target) {
        var cells = document.querySelectorAll('#labelTable .label-cell');
        for (var i = 0; i < cells.length; i++) {
            if (!__cellHasContent(cells[i])) { target = cells[i]; break; }
        }
    }
    if (!target) { __notify('没有可用的空单元格，请先插入行/列或点击选中单元格', 'warning'); return; }
    var content = __ensureCellContent(target);
    content.textContent = '[' + label + ']';
    content.dataset.field = field;
    if (field === 'qrcode' && !content.dataset.barcodeWidth) {
        content.dataset.barcodeWidth = '25';
        content.dataset.barcodeHeight = '25';
    }
    document.querySelectorAll('.label-cell').forEach(function(x) { x.classList.remove('selected'); });
    target.classList.add('selected');
    selectedCell = target;
    selectedCells = [target];
    updateCellProperties();
    saveTemplateToStorage();
    __refreshCellDraggable();
}

function initTemplateDragDrop() {
    var table = document.getElementById('labelTable');
    if (!table) return;

    // 字段拖拽源 + 双击插入：使用事件委托绑定到父容器，避免重复绑定
    var fieldPanel = table.closest('.modal-body');
    if (fieldPanel && !fieldPanel._fieldDragBound) {
        fieldPanel._fieldDragBound = true;
        fieldPanel.addEventListener('dragstart', function(e) {
            var item = e.target.closest('.field-item');
            if (!item) return;
            e.dataTransfer.effectAllowed = 'copy';
            e.dataTransfer.setData('text/plain', JSON.stringify({
                field: item.dataset.field,
                label: item.dataset.label
            }));
        });
        // 双击字段插入到选中单元格
        fieldPanel.addEventListener('dblclick', function(e) {
            var item = e.target.closest('.field-item');
            if (!item) return;
            insertFieldToSelection(item.dataset.field, item.dataset.label);
        });
    }

    // 表格拖拽事件：先移除旧监听器再添加，确保不重复
    if (table._dragHandlers) {
        table.removeEventListener('dragover', table._dragHandlers.dragover);
        table.removeEventListener('dragleave', table._dragHandlers.dragleave);
        table.removeEventListener('drop', table._dragHandlers.drop);
        table.removeEventListener('click', table._dragHandlers.click);
        table.removeEventListener('dragstart', table._dragHandlers.dragstart);
        table.removeEventListener('dragend', table._dragHandlers.dragend);
        table.removeEventListener('focusin', table._dragHandlers.focusin);
        table.removeEventListener('focusout', table._dragHandlers.focusout);
    }

    table._dragHandlers = {
        // 画布内拖动：拖动有内容的单元格
        dragstart: function(e) {
            var cell = e.target.closest('.label-cell');
            if (!cell || !__cellHasContent(cell)) return;
            __cellDragSrc = cell;
            e.dataTransfer.effectAllowed = 'move';
            try { e.dataTransfer.setData('text/plain', '__cell_move__'); } catch (err) {}
        },
        dragend: function() {
            __cellDragSrc = null;
            document.querySelectorAll('.label-cell.drag-over').forEach(function(c) { c.classList.remove('drag-over'); });
            __refreshCellDraggable();
        },
        // 编辑时禁用拖拽，失焦后恢复
        focusin: function(e) {
            var cell = e.target.closest('.label-cell');
            if (cell) cell.draggable = false;
        },
        focusout: function(e) {
            var cell = e.target.closest('.label-cell');
            if (cell) cell.draggable = __cellHasContent(cell);
        },
        dragover: function(e) {
            var cell = e.target.closest('.label-cell');
            if (!cell) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = __cellDragSrc ? 'move' : 'copy';
            document.querySelectorAll('.label-cell.drag-over').forEach(function(c) { c.classList.remove('drag-over'); });
            cell.classList.add('drag-over');
        },
        dragleave: function(e) {
            var cell = e.target.closest('.label-cell');
            if (cell && !cell.contains(e.relatedTarget)) {
                cell.classList.remove('drag-over');
            }
        },
        drop: function(e) {
            var cell = e.target.closest('.label-cell');
            if (!cell) return;
            e.preventDefault();
            cell.classList.remove('drag-over');
            // 画布内移动/交换字段
            if (__cellDragSrc) {
                if (__cellDragSrc !== cell) {
                    __swapCells(__cellDragSrc, cell);
                    saveTemplateToStorage();
                }
                __cellDragSrc = null;
                __refreshCellDraggable();
                return;
            }
            // 从字段面板拖入
            try {
                var raw = e.dataTransfer.getData('text/plain');
                if (!raw || raw === '__cell_move__') return;
                var data = JSON.parse(raw);
                var content = __ensureCellContent(cell);
                content.textContent = '[' + data.label + ']';
                content.dataset.field = data.field;
                if (data.field === 'qrcode' && !content.dataset.barcodeWidth) {
                    content.dataset.barcodeWidth = '25';
                    content.dataset.barcodeHeight = '25';
                }
                saveTemplateToStorage();
                __refreshCellDraggable();
            } catch(err) { console.error('drop error', err); }
        },
        click: function(e) {
            var cell = e.target.closest('.label-cell');
            if (!cell) return;
            if (e.ctrlKey || e.metaKey) {
                // Ctrl+点击：切换多选
                var idx = selectedCells.indexOf(cell);
                if (idx >= 0) { selectedCells.splice(idx, 1); cell.classList.remove('selected'); }
                else { selectedCells.push(cell); cell.classList.add('selected'); }
                selectedCell = cell;
            } else {
                selectedCells = [cell];
                document.querySelectorAll('.label-cell').forEach(function(c) { c.classList.remove('selected'); });
                cell.classList.add('selected');
                selectedCell = cell;
            }
            updateCellProperties();
        }
    };

    table.addEventListener('dragstart', table._dragHandlers.dragstart);
    table.addEventListener('dragend', table._dragHandlers.dragend);
    table.addEventListener('focusin', table._dragHandlers.focusin);
    table.addEventListener('focusout', table._dragHandlers.focusout);
    table.addEventListener('dragover', table._dragHandlers.dragover);
    table.addEventListener('dragleave', table._dragHandlers.dragleave);
    table.addEventListener('drop', table._dragHandlers.drop);
    table.addEventListener('click', table._dragHandlers.click);

    __refreshCellDraggable();
}

function updateCellProperties() {
    if (!selectedCell) return;
    var content = selectedCell.querySelector('.cell-content');
    if (!content) return;
    document.getElementById('cellProperties').style.display = 'block';
    document.getElementById('noSelection').style.display = 'none';
    document.getElementById('cellText').value = content.textContent;
    document.getElementById('cellField').value = content.dataset.field || '';
    document.getElementById('cellColspan').value = selectedCell.colSpan || 1;

    // 条码/二维码宽高设置显示/隐藏（AA3：二维码也可控尺寸）
    var barcodeSettings = document.getElementById('barcodeSizeSettings');
    var field = content.dataset.field || '';
    if (field === 'barcode' || field === 'qrcode') {
        barcodeSettings.style.display = 'block';
        var isQr = (field === 'qrcode');
        document.getElementById('barcodeWidthLabel').textContent = isQr ? '二维码宽度(mm)' : '条码宽度(mm)';
        document.getElementById('barcodeHeightLabel').textContent = isQr ? '二维码高度(mm)' : '条码高度(mm)';
        var defW = isQr ? '25' : '50';
        var defH = isQr ? '25' : '15';
        document.getElementById('barcodeWidth').value = content.dataset.barcodeWidth || defW;
        document.getElementById('barcodeHeight').value = content.dataset.barcodeHeight || defH;
    } else {
        barcodeSettings.style.display = 'none';
    }

    // 同步左侧样式工具的值到当前单元格的实际样式
    var curFontSize = content.style.fontSize ? parseInt(content.style.fontSize) : 12;
    var fontSizeSelect = document.getElementById('fontSizeSelect');
    if (fontSizeSelect) fontSizeSelect.value = curFontSize;

    var curFontWeight = content.style.fontWeight || 'normal';
    var fontWeightSelect = document.getElementById('fontWeightSelect');
    if (fontWeightSelect) fontWeightSelect.value = curFontWeight;

    var curColor = content.style.color || '#000000';
    var textColorSelect = document.getElementById('textColorSelect');
    if (textColorSelect) {
        // 将 rgb() 颜色转为 hex
        if (curColor.startsWith('rgb')) {
            var rgb = curColor.match(/\d+/g);
            if (rgb) {
                curColor = '#' + rgb.map(function(x){ return ('0'+parseInt(x).toString(16)).slice(-2); }).join('');
            }
        }
        textColorSelect.value = curColor;
    }

    // 显示选中单元格位置（行/列/跨列）
    var posInfo = document.getElementById('cellPosInfo');
    if (posInfo) {
        var prow = parseInt(selectedCell.dataset.row) + 1;
        var pcol = parseInt(selectedCell.dataset.col) + 1;
        posInfo.textContent = '行 ' + prow + '，列 ' + pcol + (selectedCell.colSpan > 1 ? '（跨 ' + selectedCell.colSpan + ' 列）' : '');
    }

    // 同步行高
    var row = selectedCell.parentElement;
    if (row && row.tagName === 'TR') {
        var curHeight = parseInt(row.style.height) || 30;
        var rowHeightInput = document.getElementById('rowHeightInput');
        if (rowHeightInput) rowHeightInput.value = curHeight;
    }
}

var cellTextInput = document.getElementById('cellText');
if (cellTextInput) {
    cellTextInput.addEventListener('input', function() {
        if (selectedCell) {
            selectedCell.querySelector('.cell-content').textContent = this.value;
            saveTemplateToStorage();
        }
    });
}

var cellFieldSelect = document.getElementById('cellField');
if (cellFieldSelect) {
    cellFieldSelect.addEventListener('change', function() {
        if (selectedCell && this.value) {
            var labels = {
                code: '物料编码', name: '物料名称', brand: '品牌', spec: '规格', unit_name: '单位',
                category_name: '分类', stock: '库存', price: '单价', barcode: '条码',
                qrcode: '二维码', date: '日期', supplier_name: '供应商'
            };
            var content = selectedCell.querySelector('.cell-content');
            content.textContent = '[' + (labels[this.value] || this.value) + ']';
            content.dataset.field = this.value;

            // 显示/隐藏条码/二维码宽高设置（AA3：切换字段时给二维码补默认尺寸）
            if (this.value === 'barcode' || this.value === 'qrcode') {
                if (this.value === 'qrcode' && !content.dataset.barcodeWidth) {
                    content.dataset.barcodeWidth = '25';
                    content.dataset.barcodeHeight = '25';
                }
                updateCellProperties();  // 复用统一逻辑刷新尺寸面板与标签
            } else {
                document.getElementById('barcodeSizeSettings').style.display = 'none';
            }

            saveTemplateToStorage();
        }
    });
}

// 条码/二维码宽度变化（AA3：对二维码同样生效）
var barcodeWidthInput = document.getElementById('barcodeWidth');
if (barcodeWidthInput) {
    barcodeWidthInput.addEventListener('input', function() {
        if (selectedCell) {
            var content = selectedCell.querySelector('.cell-content');
            if (content.dataset.field === 'barcode' || content.dataset.field === 'qrcode') {
                content.dataset.barcodeWidth = this.value;
                saveTemplateToStorage();
            }
        }
    });
}

// 条码/二维码高度变化（AA3：对二维码同样生效）
var barcodeHeightInput = document.getElementById('barcodeHeight');
if (barcodeHeightInput) {
    barcodeHeightInput.addEventListener('input', function() {
        if (selectedCell) {
            var content = selectedCell.querySelector('.cell-content');
            if (content.dataset.field === 'barcode' || content.dataset.field === 'qrcode') {
                content.dataset.barcodeHeight = this.value;
                saveTemplateToStorage();
            }
        }
    });
}

var cellColspanSelect = document.getElementById('cellColspan');
if (cellColspanSelect) {
    cellColspanSelect.addEventListener('change', function() {
        if (selectedCell) {
            selectedCell.colSpan = parseInt(this.value);
            saveTemplateToStorage();
        }
    });
}

function insertRow() {
    var table = document.getElementById('labelTable');
    var newRowIndex = table.rows.length; // 新行索引
    var row = table.insertRow(-1);
    row.style.height = '30px';

    // 计算实际列数
    var actualCols = 0;
    for (var i = 0; i < table.rows[0].cells.length; i++) {
        actualCols += table.rows[0].cells[i].colSpan || 1;
    }

    for (var i = 0; i < actualCols; i++) {
        var cell = row.insertCell(-1);
        cell.className = 'label-cell';
        cell.style.cssText = 'border: 1px solid #dee2e6; min-height: 25px; padding: 2px 5px; cursor: move; background: #f8f9fa;';
        cell.dataset.row = newRowIndex;
        cell.dataset.col = i;
        cell.innerHTML = '<span class="cell-content" contenteditable="true" style="display: block; font-size: 12px; overflow: hidden; white-space: normal; word-break: break-all;"></span>';
    }
    currentTemplate.rows++;
    currentTemplate.cols = actualCols;
    initTemplateDragDrop();
    saveTemplateToStorage();
}

function insertCol() {
    var table = document.getElementById('labelTable');
    var newColIndex = 0;

    // 计算实际列数
    for (var i = 0; i < table.rows[0].cells.length; i++) {
        newColIndex += table.rows[0].cells[i].colSpan || 1;
    }

    for (var i = 0; i < table.rows.length; i++) {
        var row = table.rows[i];
        var cell = row.insertCell(-1);
        cell.className = 'label-cell';
        cell.style.cssText = 'border: 1px solid #dee2e6; min-height: 25px; padding: 2px 5px; cursor: move; background: #f8f9fa;';
        cell.dataset.row = i;
        cell.dataset.col = newColIndex;
        cell.innerHTML = '<span class="cell-content" contenteditable="true" style="display: block; font-size: 12px; overflow: hidden; white-space: normal; word-break: break-all;"></span>';
    }
    currentTemplate.cols++;
    initTemplateDragDrop();
    saveTemplateToStorage();
}

function deleteSelectedRow() {
    if (selectedCell) {
        var row = selectedCell.parentElement;
        var table = document.getElementById('labelTable');
        if (row && row.tagName === 'TR' && table.rows.length > 1) {
            row.parentElement.removeChild(row);
            currentTemplate.rows--;
            selectedCell = null;
            document.getElementById('cellProperties').style.display = 'none';
            document.getElementById('noSelection').style.display = 'block';
            saveTemplateToStorage();
        } else if (table.rows.length <= 1) {
            __notify('至少需要保留一行', 'warning');
        }
    }
}

function deleteRow() {
    var table = document.getElementById('labelTable');
    if (table.rows.length <= 1) {
        __notify('至少需要保留一行', 'warning');
        return;
    }

    var rowIndex = table.rows.length - 1; // 默认删除最后一行
    if (selectedCell) {
        var row = selectedCell.parentElement;
        if (row && row.tagName === 'TR') {
            rowIndex = row.rowIndex;
        }
    }

    table.deleteRow(rowIndex);
    currentTemplate.rows--;
    selectedCell = null;
    document.getElementById('cellProperties').style.display = 'none';
    document.getElementById('noSelection').style.display = 'block';
    saveTemplateToStorage();
}

function deleteCol() {
    var table = document.getElementById('labelTable');

    // 计算实际列数（考虑跨列）
    var actualCols = 0;
    for (var i = 0; i < table.rows[0].cells.length; i++) {
        actualCols += table.rows[0].cells[i].colSpan || 1;
    }

    if (actualCols <= 1) {
        __notify('至少需要保留一列', 'warning');
        return;
    }

    var colIndex = actualCols - 1; // 默认删除最后一列
    if (selectedCell) {
        // 计算选中单元格的实际列索引
        var tempIndex = 0;
        for (var i = 0; i < selectedCell.cellIndex; i++) {
            tempIndex += table.rows[0].cells[i].colSpan || 1;
        }
        colIndex = tempIndex + (selectedCell.colSpan || 1) - 1;
    }

    // 从后往前遍历每行，删除指定列
    for (var i = 0; i < table.rows.length; i++) {
        var row = table.rows[i];

        // 计算该行的实际列索引
        var currentColIndex = 0;
        var targetCellIndex = -1;
        for (var j = 0; j < row.cells.length; j++) {
            var span = row.cells[j].colSpan || 1;
            if (currentColIndex + span > colIndex) {
                targetCellIndex = j;
                break;
            }
            currentColIndex += span;
        }

        if (targetCellIndex >= 0 && row.cells[targetCellIndex]) {
            var cell = row.cells[targetCellIndex];
            if (cell.colSpan > 1) {
                // 合并单元格：减少跨度，如果只剩1则删除
                cell.colSpan--;
                if (cell.colSpan === 1) {
                    row.deleteCell(targetCellIndex);
                }
            } else {
                row.deleteCell(targetCellIndex);
            }
        }
    }

    currentTemplate.cols--;
    selectedCell = null;
    document.getElementById('cellProperties').style.display = 'none';
    document.getElementById('noSelection').style.display = 'block';
    saveTemplateToStorage();
}

function setTextAlign(align) {
    if (selectedCell) {
        selectedCell.querySelector('.cell-content').style.textAlign = align;
        saveTemplateToStorage();
    }
}

// 垂直对齐（标签设计器可用性增强 AA3）：作用于 td 的 vertical-align，支持多选
function setVerticalAlign(align) {
    var cells = __getTargetCells();
    if (!cells.length) {
        __notify('请先点击选中单元格（Ctrl+点击可多选）', 'warning');
        return;
    }
    cells.forEach(function(cell) {
        cell.style.verticalAlign = align;
        var content = cell.querySelector('.cell-content');
        if (content) content.style.verticalAlign = align;
    });
    saveTemplateToStorage();
}

function applyFontSizeToCell(cell, sizeVal) {
    var content = cell.querySelector('.cell-content');
    if (!content) return;
    var px = parseInt(sizeVal);
    content.style.fontSize = px + 'px';
    // 自动撑高行，避免大字体被截断
    var row = cell.parentElement;
    if (row && row.tagName === 'TR') {
        var minH = Math.max(px + 10, 30);
        row.style.height = minH + 'px';
        // 同步行高输入框
        var rowHeightInput = document.getElementById('rowHeightInput');
        if (rowHeightInput) rowHeightInput.value = minH;
    }
}

function applyRowHeight() {
    var cells = __getTargetCells();
    if (!cells.length) {
        __notify('请先点击选中一个单元格', 'warning');
        return;
    }
    var input = document.getElementById('rowHeightInput');
    var h = parseInt(input.value);
    if (!h || h < 20) { h = 20; input.value = 20; }
    if (h > 200) { h = 200; input.value = 200; }
    var applied = false;
    cells.forEach(function(cell) {
        var row = cell.parentElement;
        if (row && row.tagName === 'TR') { row.style.height = h + 'px'; applied = true; }
    });
    if (applied) { saveTemplateToStorage(); }
}

document.addEventListener('DOMContentLoaded', function() {
    var fontSizeSelect = document.getElementById('fontSizeSelect');
    if (fontSizeSelect) {
        fontSizeSelect.addEventListener('change', function() {
            var cells = __getTargetCells();
            if (!cells.length) return;
            cells.forEach(function(cell) { applyFontSizeToCell(cell, fontSizeSelect.value); });
            saveTemplateToStorage();
        });
    }

    var fontWeightSelect = document.getElementById('fontWeightSelect');
    if (fontWeightSelect) {
        fontWeightSelect.addEventListener('change', function() {
            var cells = __getTargetCells();
            if (!cells.length) return;
            cells.forEach(function(cell) {
                var content = cell.querySelector('.cell-content');
                if (content) content.style.fontWeight = fontWeightSelect.value;
            });
            saveTemplateToStorage();
        });
    }

    var textColorSelect = document.getElementById('textColorSelect');
    if (textColorSelect) {
        textColorSelect.addEventListener('input', function() {
            var cells = __getTargetCells();
            if (!cells.length) return;
            cells.forEach(function(cell) {
                var content = cell.querySelector('.cell-content');
                if (content) content.style.color = textColorSelect.value;
            });
            saveTemplateToStorage();
        });
    }
});

function changeLabelSize() {
    var size = document.getElementById('labelSizeSelect').value;
    var customSizeDiv = document.getElementById('customSize');
    var canvas = document.getElementById('labelCanvas');

    if (size === 'custom') {
        customSizeDiv.style.display = 'inline';
    } else {
        customSizeDiv.style.display = 'none';
        var sizes = { small: { w: 40, h: 20 }, medium: { w: 60, h: 40 }, large90: { w: 90, h: 50 }, large: { w: 100, h: 50 } };
        currentTemplate.labelWidth = sizes[size].w;
        currentTemplate.labelHeight = sizes[size].h;
        updateCanvasSize();
    }
}

function applyCustomSize() {
    currentTemplate.labelWidth = parseInt(document.getElementById('customWidth').value) || 60;
    currentTemplate.labelHeight = parseInt(document.getElementById('customHeight').value) || 40;
    updateCanvasSize();
}

function updateCanvasSize() {
    var canvas = document.getElementById('labelCanvas');
    var scale = 4;
    canvas.style.width = (currentTemplate.labelWidth * scale) + 'px';
    canvas.style.height = (currentTemplate.labelHeight * scale) + 'px';
    __syncZoomWrap();
}

// ==================== 画布缩放 / 全屏（标签设计器可用性增强 AA5） ====================
var canvasZoom = 1;
var CANVAS_BASE_SCALE = 4;  // 画布基础像素/毫米（与 updateCanvasSize 一致）

function __syncZoomWrap() {
    var canvas = document.getElementById('labelCanvas');
    var wrap = document.getElementById('labelCanvasZoomWrap');
    if (!canvas || !wrap) return;
    // transform 不影响布局，offsetWidth/Height 始终是未缩放的基础尺寸
    var baseW = canvas.offsetWidth || (currentTemplate.labelWidth * CANVAS_BASE_SCALE);
    var baseH = canvas.offsetHeight || (currentTemplate.labelHeight * CANVAS_BASE_SCALE);
    canvas.style.transform = 'scale(' + canvasZoom + ')';
    canvas.style.transformOrigin = 'top left';
    // 预留缩放后的占位，保证视口滚动区域正确
    wrap.style.width = Math.round(baseW * canvasZoom) + 'px';
    wrap.style.height = Math.round(baseH * canvasZoom) + 'px';
    var lbl = document.getElementById('canvasZoomLabel');
    if (lbl) lbl.textContent = Math.round(canvasZoom * 100) + '%';
}

function setCanvasZoom(z) {
    canvasZoom = Math.max(0.4, Math.min(3, z));
    __syncZoomWrap();
}

function zoomCanvas(delta) { setCanvasZoom(canvasZoom + delta); }
function resetCanvasZoom() { setCanvasZoom(1); }

function fitCanvasZoom() {
    var viewport = document.getElementById('labelCanvasViewport');
    if (!viewport) return;
    var baseW = currentTemplate.labelWidth * CANVAS_BASE_SCALE;
    var avail = viewport.clientWidth - 40;
    if (baseW > 0 && avail > 0) setCanvasZoom(avail / baseW);
}

function toggleDesignerFullscreen() {
    var dlg = document.querySelector('#labelTemplateModal .modal-dialog');
    if (!dlg) return;
    dlg.classList.toggle('modal-fullscreen');
    var viewport = document.getElementById('labelCanvasViewport');
    if (viewport) viewport.style.maxHeight = dlg.classList.contains('modal-fullscreen') ? '78vh' : '52vh';
    setTimeout(fitCanvasZoom, 200);
}

// 收集当前画布为模板布局对象（新建/更新共用，标签设计器可用性增强 AA2）
function __collectTemplateData() {
    reindexLabelCells();  // BUG-2026-09-08-001：序列化前重排坐标，杜绝越界残留
    var cells = [];
    document.querySelectorAll('.label-cell').forEach(function(cell) {
        var content = cell.querySelector('.cell-content');
        if (!content) return;
        var cellData = {
            row: cell.dataset.row,
            col: cell.dataset.col,
            text: content.textContent,
            field: content.dataset.field || '',
            style: {
                fontSize: content.style.fontSize,
                fontWeight: content.style.fontWeight,
                color: content.style.color,
                textAlign: content.style.textAlign,
                verticalAlign: content.style.verticalAlign || cell.style.verticalAlign || ''
            },
            colSpan: cell.colSpan
        };
        if (content.dataset.field === 'barcode' || content.dataset.field === 'qrcode') {
            cellData.barcodeWidth = content.dataset.barcodeWidth || (content.dataset.field === 'qrcode' ? '25' : '50');
            cellData.barcodeHeight = content.dataset.barcodeHeight || (content.dataset.field === 'qrcode' ? '25' : '15');
        }
        cells.push(cellData);
    });

    var rowHeights = [];
    var table = document.getElementById('labelTable');
    for (var i = 0; i < table.rows.length; i++) {
        rowHeights.push(parseInt(table.rows[i].style.height) || 30);
    }

    return {
        rows: currentTemplate.rows,
        cols: currentTemplate.cols,
        cells: cells,
        rowHeights: rowHeights,
        labelWidth: currentTemplate.labelWidth,
        labelHeight: currentTemplate.labelHeight
    };
}

function __notify(msg, type) {
    if (typeof showToast === 'function') { showToast(msg, type || 'info'); }
    else { alert(msg); }  // allow-alert
}

// LABEL-FIX-2026-09-29-004：尺寸选择器为 custom 时，保存前先把输入框的值
// 同步进 currentTemplate，避免用户改了数字没点「应用」导致保存尺寸与界面不符
function __syncCustomSizeBeforeSave() {
    var sizeSelect = document.getElementById('labelSizeSelect');
    if (sizeSelect && sizeSelect.value === 'custom') {
        applyCustomSize();
    }
}

// 保存：已载入模板则原地更新（含尺寸），否则按"另存为"新建
function saveTemplate() {
    if (!__canWriteLabelTemplate()) return;
    try { __syncCustomSizeBeforeSave(); }
    catch (err) { __notify(err.message || '标签尺寸无效', 'danger'); return; }
    if (currentTemplateId) { return updateExistingTemplate(); }
    return saveAsTemplate();
}

// 新建成功回包没有 id，使用提交时的唯一名称在列表中定位。
function __templateNameForSave() {
    var input = document.getElementById('templateNameInput');
    var name = input.value.trim();
    if (!name) {
        input.focus();
        __notify('请输入模板名称', 'warning');
        return null;
    }
    return name;
}

function saveAsTemplate() {
    if (!__canWriteLabelTemplate()) return;
    var templateName = __templateNameForSave();
    if (!templateName) return;
    return __runLabelTemplateWrite(function() {
        __syncCustomSizeBeforeSave();
        var templateData = __collectTemplateData();
        var dbData = new FormData();
        dbData.append('name', templateName);
        dbData.append('width', currentTemplate.labelWidth);
        dbData.append('height', currentTemplate.labelHeight);
        dbData.append('cols', currentTemplate.cols);
        dbData.append('rows', currentTemplate.rows);
        dbData.append('layout', JSON.stringify(templateData));
        return WMS.api.postRaw('/label_template/add', dbData).then(__requireTemplateSuccess).then(function() {
            try { localStorage.removeItem('labelTemplateDraft'); } catch (e) {}
            __notify('模板"' + templateName + '"已保存', 'success');
            return loadTemplateList({name: templateName}, true);
        });
    });
}

function updateExistingTemplate() {
    return __runLabelTemplateWrite(function() {
        var templateData = __collectTemplateData();
        var templateId = currentTemplateId;
        if (!templateId) throw new Error('请先加载要更新的模板');
        var payload = {
            layout: templateData,
            width: currentTemplate.labelWidth,
            height: currentTemplate.labelHeight,
            cols: currentTemplate.cols,
            rows: currentTemplate.rows
        };
        return WMS.api.postRaw('/label_template/' + templateId + '/save_layout', payload)
        .then(__requireTemplateSuccess).then(function() {
            try { localStorage.removeItem('labelTemplateDraft'); } catch (e) {}
            __notify('模板已更新', 'success');
            return loadTemplateList({id: templateId}, true);
        });
    });
}

function setDefaultTemplate() {
    if (!__canWriteLabelTemplate()) return;
    var templateId = currentTemplateId;
    if (!templateId) { __notify('请先选择要设为默认的模板', 'warning'); return; }
    return __runLabelTemplateWrite(function() {
        return WMS.api.postRaw('/label_template/' + templateId + '/set_default', null)
        .then(__requireTemplateSuccess).then(function() {
            __notify('已设为默认模板', 'success');
            return loadTemplateList({id: templateId}, true);
        });
    });
}

// 列表与详情共用代次，任何新选择或本地设计均使旧回包失效。
function loadTemplateList(preferred, afterWrite) {
    if (labelTemplateWriteBusy && !afterWrite) return;
    var generation = ++labelTemplateGeneration;
    labelTemplateLoading = true;
    labelTemplateLoadFailed = false;
    currentTemplateId = null;
    document.getElementById('templateNameInput').value = '';
    var select = document.getElementById('templateSelect');
    select.innerHTML = '<option value="">-- 加载中... --</option>';
    __labelTemplateStatus('正在加载模板列表…');
    return WMS.api.getRaw('/label_template/api/list').then(function(res) {
        if (generation !== labelTemplateGeneration) return;
        __requireTemplateSuccess(res);
        if (!Array.isArray(res.templates)) throw new Error('模板列表响应无效');
        select.innerHTML = '<option value="">-- 选择模板 / 新设计 --</option>';
        var selected = null;
        res.templates.forEach(function(t) {
            var opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.name + ' (' + t.width + 'x' + t.height + 'mm)';
            select.appendChild(opt);
            if (preferred && ((preferred.id != null && String(preferred.id) === String(t.id)) ||
                (preferred.name != null && preferred.name === t.name))) selected = t;
        });
        if (!selected && preferred) throw new Error('操作已成功，但列表中未找到该模板，请重新选择');
        if (!selected) selected = res.templates.find(function(t) { return t.is_default; }) || res.templates[0];
        if (!selected) {
            labelTemplateLoading = false;
            restoreTemplateDraft(afterWrite);
            __labelTemplateStatus('暂无已保存模板，可编辑并保存新设计');
            return;
        }
        return switchTemplateById(selected.id, afterWrite);
    }).catch(function(err) {
        if (generation !== labelTemplateGeneration) return;
        labelTemplateLoading = false;
        labelTemplateLoadFailed = true;
        select.innerHTML = '<option value="">-- 加载失败，请重开设计器重试 --</option>';
        __labelTemplateStatus('加载模板列表失败：' + err.message);
        __notify('加载模板列表失败：' + err.message, 'danger');
    });
}

function switchTemplate() {
    var select = document.getElementById('templateSelect');
    if (labelTemplateWriteBusy) {
        select.value = currentTemplateId == null ? '' : currentTemplateId;
        return;
    }
    return switchTemplateById(select.value);
}

function switchTemplateById(templateId, afterWrite) {
    if (labelTemplateWriteBusy && !afterWrite) return;
    var generation = ++labelTemplateGeneration;
    var nameInput = document.getElementById('templateNameInput');
    var select = document.getElementById('templateSelect');
    currentTemplateId = null;
    nameInput.value = '';
    select.value = templateId || '';
    labelTemplateLoadFailed = false;
    labelTemplateLoading = !!templateId;
    if (!templateId) {
        __labelTemplateStatus('当前画布作为新设计，保存时新建模板');
        return;
    }
    __labelTemplateStatus('正在加载所选模板，完成前不能保存…');
    return WMS.api.getRaw('/label_template/api/' + encodeURIComponent(templateId) + '/detail')
    .then(function(res) {
        if (generation !== labelTemplateGeneration) return;
        __requireTemplateSuccess(res);
        if (!res.template || String(res.template.id) !== String(templateId)) throw new Error('模板详情响应无效');
        loadTemplateToEditor(res.template);
        nameInput.value = res.template.name || '';
        currentTemplateId = res.template.id;
        labelTemplateLoading = false;
        __labelTemplateStatus('已载入模板：' + nameInput.value);
    }).catch(function(err) {
        if (generation !== labelTemplateGeneration) return;
        labelTemplateLoading = false;
        labelTemplateLoadFailed = true;
        __labelTemplateStatus('加载模板失败：' + err.message);
        __notify('加载模板失败：' + err.message, 'danger');
    });
}

function __labelFieldKey(field) {
    var aliases = {unit: 'unit_name', category: 'category_name', supplier: 'supplier_name'};
    return Object.prototype.hasOwnProperty.call(aliases, field) ? aliases[field] : field;
}

function __labelFieldText(field) {
    var labels = {code: '物料编码', name: '物料名称', spec: '规格', brand: '品牌',
        unit_name: '单位', category_name: '分类', supplier_name: '供应商',
        stock: '库存', price: '单价', barcode: '条码', qrcode: '二维码', date: '日期'};
    return '[' + (Object.prototype.hasOwnProperty.call(labels, field) ? labels[field] : field) + ']';
}

// 加载模板到编辑器
function loadTemplateToEditor(template) {
    var layout = template.layout || template;
    function dimension(values, fallback, integer) {
        for (var i = 0; i < values.length; i++) {
            var value = Number(values[i]);
            if (Number.isFinite(value) && value > 0 && (!integer || Number.isInteger(value))) return value;
        }
        return fallback;
    }
    currentTemplate = {
        rows: dimension([layout.rows, template.rows], 3, true),
        cols: dimension([layout.cols, template.cols], 2, true),
        labelWidth: dimension([layout.width, layout.labelWidth, template.width, template.labelWidth], 60),
        labelHeight: dimension([layout.height, layout.labelHeight, template.height, template.labelHeight], 40)
    };

    var sizeSelect = document.getElementById('labelSizeSelect');
    var customSizeDiv = document.getElementById('customSize');
    if (sizeSelect) {
        var w = currentTemplate.labelWidth, h = currentTemplate.labelHeight;
        if (w === 40 && h === 20) { sizeSelect.value = 'small'; }
        else if (w === 60 && h === 40) { sizeSelect.value = 'medium'; }
        else if (w === 90 && h === 50) { sizeSelect.value = 'large90'; }
        else if (w === 100 && h === 50) { sizeSelect.value = 'large'; }
        else {
            sizeSelect.value = 'custom';
            if (customSizeDiv) customSizeDiv.style.display = 'inline';
            var cwInput = document.getElementById('customWidth');
            var chInput = document.getElementById('customHeight');
            if (cwInput) cwInput.value = w;
            if (chInput) chInput.value = h;
        }
    }

    var table = document.getElementById('labelTable');
    table.innerHTML = '';
    table._dragDelegated = false;

    // 创建行
    for (var r = 0; r < currentTemplate.rows; r++) {
        var row = table.insertRow(-1);
        var rh = (layout.rowHeights && layout.rowHeights[r]) ? layout.rowHeights[r] : 30;
        row.style.height = rh + 'px';
    }

    if (layout.cells && layout.cells.length > 0) {
        layout.cells.forEach(function(cellData) {
            var r = parseInt(cellData.row);
            var c = parseInt(cellData.col);
            if (r >= 0 && r < table.rows.length) {
                var row = table.rows[r];
                // 确保该行有足够的单元格
                while (row.cells.length <= c) {
                    var newCell = row.insertCell(-1);
                    newCell.className = 'label-cell';
                    newCell.style.cssText = 'border: 1px solid #dee2e6; min-height: 25px; padding: 2px 5px; cursor: move; background: #f8f9fa;';
                    newCell.innerHTML = '<span class="cell-content" contenteditable="true" style="display: block; font-size: 12px; overflow: hidden; white-space: normal; word-break: break-all;"></span>';
                }
                var cell = row.cells[c];
                cell.dataset.row = r;
                cell.dataset.col = c;

                {
                    cell.innerHTML = '';
                    var content = document.createElement('span');
                    content.className = 'cell-content';
                    content.setAttribute('contenteditable', 'true');
                    content.style.cssText = 'display: block; overflow: hidden; white-space: normal; word-break: break-all;';
                    var cellStyle = cellData.style || {};
                    content.style.fontSize = (parseFloat(cellStyle.fontSize) || 12) + 'px';
                    content.style.fontWeight = cellStyle.fontWeight || 'normal';
                    content.style.color = cellStyle.color || '#000';
                    content.style.textAlign = cellStyle.textAlign || 'left';
                    var fieldKey = __labelFieldKey(cellData.field || '');
                    content.textContent = cellData.text == null || cellData.text === ''
                        ? (fieldKey ? __labelFieldText(fieldKey) : '') : String(cellData.text);
                    cell.appendChild(content);
                    content.dataset.field = fieldKey;
                    // 恢复垂直对齐（AA3）
                    if (cellData.style && cellData.style.verticalAlign) {
                        cell.style.verticalAlign = cellData.style.verticalAlign;
                        content.style.verticalAlign = cellData.style.verticalAlign;
                    }
                    // 恢复条码/二维码宽高（AA3：含二维码）
                    if (cellData.field === 'barcode' || cellData.field === 'qrcode') {
                        content.dataset.barcodeWidth = cellData.barcodeWidth || (cellData.field === 'qrcode' ? '25' : '50');
                        content.dataset.barcodeHeight = cellData.barcodeHeight || (cellData.field === 'qrcode' ? '25' : '15');
                    }
                    if (cellData.colSpan > 1) cell.colSpan = cellData.colSpan;
                }
            }
        });
    } else {
        // 创建空白的单元格
        for (var r = 0; r < currentTemplate.rows; r++) {
            var row = table.rows[r];
            for (var c = 0; c < currentTemplate.cols; c++) {
                var cell = row.insertCell(-1);
                cell.className = 'label-cell';
                cell.style.cssText = 'border: 1px solid #dee2e6; min-height: 25px; padding: 2px 5px; cursor: move; background: #f8f9fa;';
                cell.dataset.row = r;
                cell.dataset.col = c;
                cell.innerHTML = '<span class="cell-content" contenteditable="true" style="display: block; font-size: 12px; overflow: hidden; white-space: normal; word-break: break-all;"></span>';
            }
        }
    }

    // 补齐每行缺失的单元格
    for (var r = 0; r < table.rows.length; r++) {
        var row = table.rows[r];
        var usedCols = 0;
        for (var ci = 0; ci < row.cells.length; ci++) {
            usedCols += (row.cells[ci].colSpan || 1);
        }
        while (usedCols < currentTemplate.cols) {
            var cell = row.insertCell(-1);
            cell.className = 'label-cell';
            cell.style.cssText = 'border: 1px solid #dee2e6; min-height: 25px; padding: 2px 5px; cursor: move; background: #f8f9fa;';
            cell.dataset.row = r;
            cell.dataset.col = row.cells.length - 1;
            cell.innerHTML = '<span class="cell-content" contenteditable="true" style="display: block; font-size: 12px; overflow: hidden; white-space: normal; word-break: break-all;"></span>';
            usedCols++;
        }
    }

    initTemplateDragDrop();
    updateCanvasSize();  // 让画布反映模板宽高比并同步缩放占位（AA5）
    if (!__applyingHistory) { __resetHistory(); }
}

// 删除模板
function deleteTemplate() {
    if (!__canWriteLabelTemplate()) return;
    var templateId = currentTemplateId;
    if (!templateId) { __notify('请选择要删除的模板', 'warning'); return; }
    return __runLabelTemplateWrite(function() {
        if (!confirm('确定要删除该模板吗？')) return;
        return WMS.api.postRaw('/label_template/' + templateId + '/delete', null)
        .then(__requireTemplateSuccess).then(function() {
            currentTemplateId = null;
            document.getElementById('templateNameInput').value = '';
            __notify('模板已删除', 'success');
            return loadTemplateList(null, true);
        });
    });
}

function clearTemplate() {
    if (labelTemplateWriteBusy) return;
    if (confirm('确定清空当前模板吗？（可用 Ctrl+Z 撤销）')) {
        __invalidateTemplateLoad();
        var table = document.getElementById('labelTable');
        var newCell = document.createElement('td');
        newCell.className = 'label-cell';
        newCell.setAttribute('style', 'border: 1px solid #dee2e6; min-height: 25px; padding: 2px 5px; cursor: move; background: #f8f9fa;');
        newCell.setAttribute('data-row', '0');
        newCell.setAttribute('data-col', '0');
        newCell.innerHTML = '<span class="cell-content" contenteditable="true" style="display: block; font-size: 12px; overflow: hidden; white-space: normal; word-break: break-all;">点击输入内容或拖拽字段</span>';

        var newRow = document.createElement('tr');
        newRow.style.height = '30px';
        newRow.appendChild(newCell);

        table.innerHTML = '';
        table.appendChild(newRow);
        table._dragDelegated = false; // 重置委托标志

        currentTemplate.rows = 1;
        currentTemplate.cols = 1;
        selectedCell = null;
        document.getElementById('cellProperties').style.display = 'none';
        document.getElementById('noSelection').style.display = 'block';
        // 清空后视为新设计：保存走"另存为"，避免误覆盖已载入模板（AA2/AA5）
        currentTemplateId = null;
        document.getElementById('templateSelect').value = '';
        document.getElementById('templateNameInput').value = '';
        initTemplateDragDrop();
        // AA5：把清空前快照入撤销栈并写草稿，使清空可撤销
        saveTemplateToStorage();
    }
}

// ==================== 所见即所得预览/打印（标签设计器可用性增强 AA1） ====================
// 设计器内置预览/打印此前只输出占位文字（条码/二维码渲染成「[条码]」文本），
// 与真实批量打印页（print_batch_labels.html，渲染 <img>）严重脱节。
// 这里统一改为：文本字段填示例值、条码/二维码渲染真实图片，做到所见即所得。

// 示例数据（预览/打印用，可在预览弹窗切换回占位符）
var labelSampleData = {
    code: 'MAT-0001',
    name: '深沟球轴承 6204-2RS',
    spec: '内径20×外径47×厚14',
    unit_name: '套',
    category_name: '轴承',
    stock: '128',
    price: '¥12.50',
    barcode: 'MAT-0001',
    qrcode: 'MAT-0001',
    date: '2026-09-10',
    supplier_name: '鑫达五金'
};
var previewUseSample = true;

function togglePreviewSample(checked) {
    previewUseSample = !!checked;
    __renderPreview();
}

// 序列化当前画布为统一模型（预览/打印复用），保证两处渲染一致
function __buildLabelModel() {
    reindexLabelCells();
    var table = document.getElementById('labelTable');
    var cells = [];
    var rowHeights = [];
    var maxRow = -1;
    if (table) {
        for (var r = 0; r < table.rows.length; r++) {
            rowHeights.push(parseInt(table.rows[r].style.height) || 30);
        }
        table.querySelectorAll('.label-cell').forEach(function(cell) {
            var content = cell.querySelector('.cell-content');
            if (!content) return;
            var cd = {
                row: parseInt(cell.dataset.row) || 0,
                col: parseInt(cell.dataset.col) || 0,
                colSpan: cell.colSpan || 1,
                text: content.textContent,
                field: content.dataset.field || '',
                style: {
                    fontSize: content.style.fontSize || '12px',
                    fontWeight: content.style.fontWeight || 'normal',
                    color: content.style.color || '#000000',
                    textAlign: content.style.textAlign || 'left',
                    verticalAlign: content.style.verticalAlign || cell.style.verticalAlign || 'middle'
                }
            };
            if (cd.field === 'barcode' || cd.field === 'qrcode') {
                cd.barcodeWidth = content.dataset.barcodeWidth || '';
                cd.barcodeHeight = content.dataset.barcodeHeight || '';
            }
            if (cd.row > maxRow) maxRow = cd.row;
            cells.push(cd);
        });
    }
    return {
        rows: Math.max(currentTemplate.rows, maxRow + 1),
        cols: currentTemplate.cols,
        labelWidth: currentTemplate.labelWidth,
        labelHeight: currentTemplate.labelHeight,
        cells: cells,
        rowHeights: rowHeights
    };
}

function __escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 生成单个单元格的内部 HTML（条码/二维码输出真实图片，文本字段填示例值）
// opts: { scale, unit('px'|'mm'), useSample, labelWidth, labelHeight, origin }
function __cellInnerHtml(cd, opts) {
    var field = __labelFieldKey(cd.field || '');
    var scale = opts.scale || 4;

    function codeImgHtml(kind, value) {
        var wMm, hMm, src;
        if (kind === 'barcode') {
            wMm = parseInt(cd.barcodeWidth) || 50;
            hMm = parseInt(cd.barcodeHeight) || 15;
            wMm = Math.min(wMm, opts.labelWidth * 0.9);
            src = opts.origin + '/api/barcode/' + encodeURIComponent(value);
        } else {
            if (cd.barcodeWidth) {
                wMm = parseInt(cd.barcodeWidth);
                hMm = parseInt(cd.barcodeHeight) || wMm;
            } else {
                wMm = Math.min(opts.labelWidth * 0.4, opts.labelHeight * 0.5);
                hMm = wMm;
            }
            var pxSize = Math.max(100, Math.min(400, Math.round(wMm * 3.78)));
            src = opts.origin + '/api/qrcode/' + encodeURIComponent(value) + '?size=' + pxSize;
        }
        var wCss = opts.unit === 'mm' ? (wMm + 'mm') : (Math.round(wMm * scale) + 'px');
        var hCss = opts.unit === 'mm' ? (hMm + 'mm') : (Math.min(Math.round(hMm * scale), opts.maxHeight || Infinity) + 'px');
        return '<img src="' + src + '" alt="' + __escapeHtml(value) + '" style="width:' + wCss + ';height:' + hCss + ';display:block;max-width:100%;image-rendering:pixelated;">';
    }

    if (field === 'barcode' || field === 'qrcode') {
        if (opts.useSample) {
            return codeImgHtml(field, labelSampleData[field] || labelSampleData.code);
        }
        return __escapeHtml(cd.text); // 占位模式：显示 [条码]/[二维码] 文本
    }
    var txt = cd.text;
    if (opts.useSample && field && labelSampleData[field] !== undefined) {
        txt = labelSampleData[field];
    }
    return __escapeHtml(txt);
}

// 仅渲染预览内容（不弹窗），供预览按钮与示例切换复用
function __renderPreview() {
    var preview = document.getElementById('previewContent');
    if (!preview) return;
    var scale = 4;  // 预览放大倍数
    var model = __buildLabelModel();
    var labelWidth = model.labelWidth * scale;
    var labelHeight = model.labelHeight * scale;

    var byRow = {};
    model.cells.forEach(function(cd) { (byRow[cd.row] = byRow[cd.row] || []).push(cd); });

    var totalHeight = model.rowHeights.slice(0, model.rows).reduce(function(sum, height) { return sum + (Number(height) || 30); }, 0);
    var html = '<table id="previewLabel" style="width:' + labelWidth + 'px;height:' + labelHeight + 'px;border:1px solid #000;background:white;table-layout:fixed;border-collapse:collapse;"><tbody>';
    for (var r = 0; r < model.rows; r++) {
        var rowHeight = totalHeight > 0 ? (model.rowHeights[r] || 30) / totalHeight * (labelHeight - 1) : (labelHeight - 1) / model.rows;
        html += '<tr style="height:' + rowHeight + 'px;">';
        var rowCells = (byRow[r] || []).sort(function(a, b) { return a.col - b.col; });
        rowCells.forEach(function(cd) {
            var fs = parseInt(cd.style.fontSize) || 12;
            html += '<td' + (cd.colSpan > 1 ? ' colspan="' + cd.colSpan + '"' : '') +
                ' style="border:0.3px solid #ccc;padding:2px;vertical-align:' + (cd.style.verticalAlign || 'middle') +
                ';overflow:hidden;word-break:break-all;font-size:' + (fs * 25.4 / 72 * scale) + 'px;font-weight:' + cd.style.fontWeight +
                ';color:' + cd.style.color + ';text-align:' + cd.style.textAlign + ';">' +
                __cellInnerHtml(cd, { scale: scale, unit: 'px', maxHeight: Math.max(1, rowHeight - 5), useSample: previewUseSample, labelWidth: model.labelWidth, labelHeight: model.labelHeight, origin: location.origin }) +
                '</td>';
        });
        html += '</tr>';
    }
    html += '</tbody></table>';
    preview.innerHTML = html;

    var tog = document.getElementById('previewSampleToggle');
    if (tog) tog.checked = previewUseSample;
}

function previewLabel() {
    __renderPreview();
    new bootstrap.Modal(document.getElementById('previewModal')).show();
}

function printLabels() {
    var selected = getSelectedMaterialIds();

    if (selected.length === 0) {
        __notify('请先选择要打印标签的物料（勾选表格中的复选框）', 'warning');
        return;
    }

    window.open(materialPageData.urls.printBatch + '?ids=' + selected.join(','), '_blank');
}

function printSingleLabel(id) {
    window.open(materialPageData.urls.printBatch + '?ids=' + id, '_blank');
}

function doPrint() {
    // 与预览同一数据模型渲染，条码/二维码输出真实图片（绝对地址，兼容 about:blank 打印窗）
    var model = __buildLabelModel();
    var scale = 4;
    var w = model.labelWidth;
    var h = model.labelHeight;

    var byRow = {};
    model.cells.forEach(function(cd) { (byRow[cd.row] = byRow[cd.row] || []).push(cd); });

    var totalPx = 0;
    for (var i = 0; i < model.rowHeights.length; i++) { totalPx += model.rowHeights[i]; }

    var printWindow = window.open('', '', 'width=600,height=400');
    printWindow.document.write('<!DOCTYPE html><html><head><title>标签打印</title>');
    printWindow.document.write('<style>');
    printWindow.document.write('@page { size: ' + w + 'mm ' + h + 'mm; margin: 0; }');
    printWindow.document.write('@media print { body { margin: 0; } }');
    printWindow.document.write('body { margin: 0; }');
    printWindow.document.write('table { width: ' + w + 'mm; height: ' + h + 'mm; border-collapse: collapse; table-layout: fixed; }');
    printWindow.document.write('td { border: 0.3px solid #000; padding: 1mm; overflow: hidden; word-break: break-all; }');
    printWindow.document.write('</style></head><body>');
    printWindow.document.write('<table>');
    for (var r = 0; r < model.rows; r++) {
        var rhPx = model.rowHeights[r] || 30;
        var rhMm = totalPx > 0 ? (rhPx / totalPx * h) : (h / model.rows);
        printWindow.document.write('<tr style="height: ' + rhMm.toFixed(2) + 'mm;">');
        var rowCells = (byRow[r] || []).sort(function(a, b) { return a.col - b.col; });
        rowCells.forEach(function(cd) {
            var fs = parseInt(cd.style.fontSize) || 12;
            printWindow.document.write('<td' + (cd.colSpan > 1 ? ' colspan="' + cd.colSpan + '"' : '') +
                ' style="vertical-align:' + (cd.style.verticalAlign || 'middle') + ';font-size:' + fs + 'pt;font-weight:' + cd.style.fontWeight +
                ';color:' + cd.style.color + ';text-align:' + cd.style.textAlign + ';">' +
                __cellInnerHtml(cd, { scale: scale, unit: 'mm', useSample: previewUseSample, labelWidth: w, labelHeight: h, origin: location.origin }) +
                '</td>');
        });
        printWindow.document.write('</tr>');
    }
    printWindow.document.write('</table>');
    // 等待条码/二维码图片加载后再唤起打印，避免打印出空白图
    printWindow.addEventListener('load', function() {
        printWindow.setTimeout(function() { printWindow.print(); }, 400);
    }, { once: true });
    printWindow.document.write('</body></html>');
    printWindow.document.close();
}


// Explicit page actions; no string compilation or global-name lookup.
const materialPageActions = {
    applyCustomSize: function(node) { applyCustomSize(); },
    applyRowHeight: function(node) { applyRowHeight(); },
    changeLabelSize: function(node) { changeLabelSize(); },
    clearSelectedCells: function(node) { clearSelectedCells(); },
    clearTemplate: function(node) { clearTemplate(); },
    deleteCol: function(node) { deleteCol(); },
    deleteEditMaterialImage: function(node) { deleteEditMaterialImage(Number(node.dataset.materialId)); },
    deleteRow: function(node) { deleteRow(); },
    deleteSelectedRow: function(node) { deleteSelectedRow(); },
    deleteTemplate: function(node) { deleteTemplate(); },
    doPrint: function(node) { doPrint(); },
    findMaterialImage: function(node) { findMaterialImage(Number(node.dataset.materialId)); },
    fitCanvasZoom: function(node) { fitCanvasZoom(); },
    fixEmptyFields: function(node) { fixEmptyFields(); },
    insertCol: function(node) { insertCol(); },
    insertRow: function(node) { insertRow(); },
    mergeMaterialInto: function(node) { mergeMaterialInto(Number(node.dataset.materialId), node.dataset.code); },
    openLabelTemplate: function(node) { openLabelTemplate(); },
    previewLabel: function(node) { previewLabel(); },
    previewMaterialImage: function(node) { previewMaterialImage(node.src); },
    printLabels: function(node) { printLabels(); },
    redoTemplate: function(node) { redoTemplate(); },
    resetCanvasZoom: function(node) { resetCanvasZoom(); },
    resetMaterialColumns: function(node) { resetMaterialColumns(); },
    saveAsTemplate: function(node) { saveAsTemplate(); },
    saveTemplate: function(node) { saveTemplate(); },
    sendLabelsToPrintStation: function(node) { sendLabelsToPrintStation(); },
    setDefaultTemplate: function(node) { setDefaultTemplate(); },
    setTextAlign: function(node) { setTextAlign(node.dataset.materialValue); },
    setVerticalAlign: function(node) { setVerticalAlign(node.dataset.materialValue); },
    submitFilterForm: function(node) { node.form.submit(); },
    switchTemplate: function(node) { switchTemplate(); },
    toggleDesignerFullscreen: function(node) { toggleDesignerFullscreen(); },
    toggleMaterialColumnSettings: function(node) { toggleMaterialColumnSettings(); },
    toggleMaterialStatus: function(node) { toggleMaterialStatus(Number(node.dataset.materialId), node.dataset.materialValue); },
    togglePreviewSample: function(node) { togglePreviewSample(node.checked); },
    toolbarCopy: function(node) { toolbarCopy(); },
    toolbarDelete: function(node) { toolbarDelete(); },
    toolbarEdit: function(node) { toolbarEdit(); },
    toolbarFindImage: function(node) { toolbarFindImage(); },
    toolbarMerge: function(node) { toolbarMerge(); },
    toolbarPrint: function(node) { toolbarPrint(); },
    undoTemplate: function(node) { undoTemplate(); },
    uploadEditMaterialImage: function(node) { uploadEditMaterialImage(node); },
    zoomCanvas: function(node) { zoomCanvas(Number(node.dataset.materialValue)); }
};
['click', 'change', 'input'].forEach(function(eventName) {
    document.addEventListener(eventName, function(event) {
        const attribute = 'data-material-' + (eventName === 'click' ? 'action' : eventName);
        const node = event.target.closest('[' + attribute + ']');
        if (!node || node.disabled) return;
        const action = materialPageActions[node.getAttribute(attribute)];
        if (!Object.prototype.hasOwnProperty.call(materialPageActions, node.getAttribute(attribute))) return;
        if (eventName === 'click') event.preventDefault();
        action(node);
    });
});
document.addEventListener('keydown', function(event) {
    if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('img[data-material-action="previewMaterialImage"]')) {
        event.preventDefault(); event.target.click();
    }
});
