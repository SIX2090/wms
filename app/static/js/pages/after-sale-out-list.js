// Page code for the migrated after_sale_out list.
document.querySelectorAll('.sortable-header').forEach(function(th) {
    th.addEventListener('click', function() {
        const sortField = this.dataset.sortable;
        const url = new URL(window.location.href);
        const currentSort = url.searchParams.get('sort');
        const currentOrder = url.searchParams.get('order') || 'desc';
        url.searchParams.set('sort', sortField);
        url.searchParams.set('order', currentSort === sortField && currentOrder === 'asc' ? 'desc' : 'asc');
        url.searchParams.delete('page');
        window.location.href = url.toString();
    });
});

function toggleAll() {
    const checkAll = document.getElementById('checkAll');
    document.querySelectorAll('.order-check').forEach(cb => cb.checked = checkAll.checked);
}

function completeOrder(id) {
    return WMS.runDocumentAction('completeOrder', function() {
        return showConfirm('确认完成此售后出库单？完成后将扣减库存。').then(function(ok) {
            if (!ok) return;
            return WMS.api.postRaw(`/after_sale_out/${id}/complete`, {})
            .then(data => {
                if (data.status === 'success') {
                    showToast('操作成功', 'success');
                    location.reload();
                } else {
                    showToast('操作失败：' + data.msg, 'danger');
                }
            });
        });
    });
}

function revertOrder(id) {
    showConfirm('确认反提交该售后出库单？反提交后库存将恢复。').then(function(ok) {
        if (!ok) return;
        return WMS.api.postRaw(`/after_sale_out/${id}/revert`)
        .then(data => {
            if (data.status === 'success') {
                showToast(data.msg || '反提交成功', 'success');
                location.reload();
            } else {
                showToast('反提交失败：' + (data.msg || '未知错误'), 'danger');
            }
        });
    }).catch(function(error) { showToast('操作失败：' + error.message, 'danger'); });
}

function deleteOrder(id) {
    showConfirm('确认删除此售后出库单？').then(function(ok) {
        if (!ok) return;
        return WMS.api.postRaw(`/after_sale_out/${id}/delete`)
        .then(data => {
            if (data.status === 'success') {
                showToast('删除成功', 'success');
                location.reload();
            } else {
                showToast('删除失败：' + (data.msg || '未知错误'), 'danger');
            }
        });
    }).catch(function(error) { showToast('操作失败：' + error.message, 'danger'); });
}

function printAfterSaleOutList() {
    var checked = document.querySelectorAll('.order-check:checked');
    var ids = Array.from(checked).map(function(cb){ return cb.value; });
    if (ids.length === 0) {
        showToast('请先勾选要打印的售后出库单', 'warning');
        return;
    }
    if (ids.length === 1) {
        window.open('/after_sale_out/' + ids[0] + '/print_options', '_blank');
        return;
    }
    showToast('当前仅支持逐单打印，已打开第一张', 'info', 3000);
    window.open('/after_sale_out/' + ids[0] + '/print_options', '_blank');
}

async function submitDocumentImport(formId, fileId) {
    if (submitDocumentImport.pending) return;
    const form = document.getElementById(formId);
    const fileInput = document.getElementById(fileId);
    if (!form || !fileInput || !fileInput.files.length) return;
    const selectedFile = fileInput.files[0];
    const button = document.getElementById('afterSaleOutImportFileButton');
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
