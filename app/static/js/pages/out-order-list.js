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
            if (th) {
                th.style.opacity = '';
                th.dataset.dragMoved = '1';
                setTimeout(function() { if (th) th.dataset.dragMoved = ''; }, 0);
            }
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
            // 移动表头（toIndex 已表示插入位置前的目标索引）
            listThead.insertBefore(listDragTh, listThead.children[toIndex] || null);
            // 移动表体
            var rows = listTable.querySelectorAll('tbody tr');
            rows.forEach(function(row) {
                var cells = Array.from(row.children);
                var cell = cells[fromIndex];
                if (!cell) return;
                row.insertBefore(cell, cells[toIndex] || null);
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
    if (batchOutOrderAction._busy) return;
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
        if (!confirmed || batchOutOrderAction._busy) return;
        batchOutOrderAction._busy = true;
        WMS.api.postRaw(url, {ids: ids})
        .then(function(data) {
            if (data.status === 'success') {
                showToast(data.msg || '操作成功', 'success');
                setTimeout(function(){ location.reload(); }, 650);
            } else {
                batchOutOrderAction._busy = false;
                showToast(data.msg || '操作失败', 'danger', 5000);
            }
        })
        .catch(function(error) {
            batchOutOrderAction._busy = false;
            showToast('操作失败：' + error.message, 'danger', 5000);
        });
    });
}

async function reviewIssueRevert(button, id) {
    if (button.disabled) return;
    button.disabled = true;
    try {
        // A list row represents one material. Review all lines of the current document.
        const response = await fetch(button.dataset.reviewUrl, {credentials: 'same-origin', cache: 'no-store'});
        if (!response.ok) throw new Error('无法读取单据，请刷新列表后重试');
        const detail = new DOMParser().parseFromString(await response.text(), 'text/html');
        const message = detail.getElementById('issueRevert')?.dataset.summary;
        if (!message) throw new Error('当前单据不可撤销，请刷新列表核对状态');
        await singleOutOrderAction('/out_order/' + id + '/revert', message, {title: '撤销领料', okText: '撤销领料'});
    } catch (error) {
        showToast(error.message || '读取领料单失败', 'danger', 5000);
    } finally {
        button.disabled = false;
    }
}

function singleOutOrderAction(url, confirmMessage, options) {
    if (singleOutOrderAction._busy) return Promise.resolve();
    return showConfirm(confirmMessage, options || {title: '处理' + outOrderBusinessLabel()}).then(function(confirmed) {
        if (!confirmed || singleOutOrderAction._busy) return;
        singleOutOrderAction._busy = true;
        var submitUrl = function(targetUrl) {
            return WMS.api.postRaw(targetUrl)
            .then(function(data) {
                if (data && data.status === 'success') {
                    showToast(data.msg || '操作成功', 'success');
                    setTimeout(function(){ location.reload(); }, 650);
                } else if (data && data.status === 'warning' && Array.isArray(data.anomalies) && targetUrl.indexOf('force=true') === -1) {
                    var details = data.anomalies.map(function(a) { return (a && a.msg) ? a.msg : String(a || ''); }).filter(Boolean).join('\n');
                    var warnPrompt = (data.msg || '检测到异常提醒') + (details ? '\n' + details : '') + '\n\n确认仍要继续提交？';
                    return showConfirm(warnPrompt, {title: '异常检测提醒', okText: '确认提交'}).then(function(forceOk) {
                        if (!forceOk) {
                            singleOutOrderAction._busy = false;
                            return;
                        }
                        var sep = targetUrl.indexOf('?') >= 0 ? '&' : '?';
                        return submitUrl(targetUrl + sep + 'force=true');
                    });
                } else {
                    singleOutOrderAction._busy = false;
                    showToast((data && data.msg) || '操作失败', 'danger', 5000);
                }
            })
            .catch(function(error) {
                singleOutOrderAction._busy = false;
                showToast('操作失败：' + error.message, 'danger', 5000);
            });
        };
        return submitUrl(url);
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
