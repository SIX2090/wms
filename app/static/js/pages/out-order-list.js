// Page code for the migrated out_order list.
document.addEventListener('DOMContentLoaded', function() {
    var configNode = document.getElementById('outOrderListConfig');
    var pageConfig = configNode ? JSON.parse(configNode.textContent) : {};
    initCheckAll('outOrderTable');
    setupResizableTable({
        tableSelector: '.table-responsive-wrapper table',
        tableId: 'out-order-detail-list',
        minWidth: 70
    });

    document.querySelectorAll('.sortable-header').forEach(function(th) {
        th.addEventListener('click', function(e) {
            if (e.detail === 1 && this.dataset.dragMoved) { this.dataset.dragMoved = ''; return; }
            var sortField = this.dataset.sortable;
            if (!sortField) return;
            var currentSort = pageConfig.sortBy || 'id';
            var currentOrder = pageConfig.sortOrder || 'desc';
            var newOrder = (currentSort === sortField && currentOrder === 'asc') ? 'desc' : 'asc';
            var url = new URL(window.location.href);
            url.searchParams.set('sort', sortField);
            url.searchParams.set('order', newOrder);
            url.searchParams.set('page', '1');
            window.location.href = url.toString();
        });
    });

    // 列拖动排序
    var listTable = document.getElementById('outOrderTable');
    if (listTable) {
        var listThead = listTable.querySelector('thead tr');
        var listDragTh = null, listDragIndex = -1;

        listThead.addEventListener('dragstart', function(e) {
            var th = e.target.closest('th');
            if (!th) return;
            listDragTh = th;
            listDragIndex = Array.from(listThead.children).indexOf(th);
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', listDragIndex);
            setTimeout(function() { th.style.opacity = '0.4'; }, 0);
        });

        listThead.addEventListener('dragend', function(e) {
            var th = e.target.closest('th');
            if (th) { th.style.opacity = ''; th.dataset.dragMoved = '1'; }
            listDragTh = null;
            listDragIndex = -1;
        });

        listThead.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            var th = e.target.closest('th');
            if (!th || th === listDragTh) return;
            var rect = th.getBoundingClientRect();
            var mid = rect.left + rect.width / 2;
            if (e.clientX < mid) {
                th.style.borderLeft = '2px solid #4F46E5';
                th.style.borderRight = '';
            } else {
                th.style.borderLeft = '';
                th.style.borderRight = '2px solid #4F46E5';
            }
        });

        listThead.addEventListener('dragleave', function(e) {
            var th = e.target.closest('th');
            if (th) { th.style.borderLeft = ''; th.style.borderRight = ''; }
        });

        listThead.addEventListener('drop', function(e) {
            e.preventDefault();
            var th = e.target.closest('th');
            if (!th || !listDragTh || th === listDragTh) return;
            th.style.borderLeft = ''; th.style.borderRight = '';
            var fromIndex = listDragIndex;
            var toIndex = Array.from(listThead.children).indexOf(th);
            var rect = th.getBoundingClientRect();
            if (e.clientX >= rect.left + rect.width / 2) toIndex++;
            if (fromIndex === toIndex || fromIndex === toIndex - 1) return;
            // 移动表头
            if (toIndex > fromIndex) {
                listThead.insertBefore(listDragTh, listThead.children[toIndex + 1] || null);
            } else {
                listThead.insertBefore(listDragTh, listThead.children[toIndex]);
            }
            // 移动表体
            var rows = listTable.querySelectorAll('tbody tr');
            rows.forEach(function(row) {
                var cells = Array.from(row.children);
                var cell = cells[fromIndex];
                if (!cell) return;
                if (toIndex > fromIndex) {
                    row.insertBefore(cell, cells[toIndex + 1] || null);
                } else {
                    row.insertBefore(cell, cells[toIndex]);
                }
            });
        });

        Array.from(listThead.children).forEach(function(th) {
            th.draggable = true;
            th.style.cursor = 'grab';
        });
    }
});

function changePerPage(perPage) {
    var url = new URL(window.location.href);
    url.searchParams.set('per_page', perPage);
    url.searchParams.set('page', '1');
    window.location.href = url.toString();
}

function selectedOrderIds(tableId) {
    var ids = [];
    document.querySelectorAll('#' + tableId + ' .check-item:checked').forEach(function(cb) {
        if (ids.indexOf(cb.value) === -1) ids.push(cb.value);
    });
    return ids;
}

function outOrderBusinessLabel() {
    var table = document.getElementById('outOrderTable');
    return (table && table.getAttribute('data-business-label')) || '领料单';
}

function batchOutOrderAction(url, emptyMessage, confirmMessage) {
    var ids = selectedOrderIds('outOrderTable');
    if (!ids.length) {
        showToast(emptyMessage, 'warning');
        return;
    }
    if (ids.length > 100) {
        showToast('单次批量操作不能超过 100 条，请分批处理', 'warning', 5000);
        return;
    }
    showConfirm(confirmMessage, {title: '批量处理' + outOrderBusinessLabel()}).then(function(confirmed) {
        if (!confirmed) return;
        WMS.api.postRaw(url, {ids: ids})
        .then(function(data) {
            if (data.status === 'success') {
                showToast(data.msg || '操作成功', 'success');
                setTimeout(function(){ location.reload(); }, 650);
            } else {
                showToast(data.msg || '操作失败', 'danger', 5000);
            }
        })
        .catch(function(error) { showToast('操作失败：' + error.message, 'danger', 5000); });
    });
}

function singleOutOrderAction(url, confirmMessage) {
    showConfirm(confirmMessage, {title: '处理' + outOrderBusinessLabel()}).then(function(confirmed) {
        if (!confirmed) return;
        WMS.api.postRaw(url)
        .then(function(data) {
            if (data.status === 'success') {
                showToast(data.msg || '操作成功', 'success');
                setTimeout(function(){ location.reload(); }, 650);
            } else {
                showToast(data.msg || '操作失败', 'danger', 5000);
            }
        })
        .catch(function(error) { showToast('操作失败：' + error.message, 'danger', 5000); });
    });
}

async function submitDocumentImport(formId, fileId) {
    if (submitDocumentImport.pending) return;
    const form = document.getElementById(formId);
    const fileInput = document.getElementById(fileId);
    if (!form || !fileInput || !fileInput.files.length) return;
    const selectedFile = fileInput.files[0];
    const button = document.getElementById('outOrderImportFileButton');
    const wasDisabled = fileInput.disabled;
    const buttonWasDisabled = button && button.disabled;
    let refreshing = false;
    submitDocumentImport.pending = true;
    try {
        // Capture the file before disabling its form control.
        const formData = new FormData(form);
        fileInput.disabled = true;
        if (button) button.disabled = true;
        await WMS.api.postRaw(form.action, formData)
        .then(function(data) {
            if (data.status === 'success') {
                refreshing = true;
                showToast(data.msg || '导入成功', 'success', 3600);
                setTimeout(function(){ location.reload(); }, 900);
            } else {
                showToast(data.msg || '导入失败', 'danger', 5000);
            }
        });
    } catch (error) {
        showToast('导入失败：' + ((error && error.message) || '请求失败，请稍后重试'), 'danger', 5000);
    } finally {
        if (fileInput.files[0] === selectedFile) fileInput.value = '';
        if (!refreshing) {
            submitDocumentImport.pending = false;
            fileInput.disabled = wasDisabled;
            if (button) button.disabled = buttonWasDisabled;
        }
    }
}
