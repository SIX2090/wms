document.addEventListener('DOMContentLoaded', function() {
    initCheckAll('warehouseTable');

    // 导入仓库
    var importForm = document.getElementById('importForm');
    if (importForm) {
        importForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var btn = this.querySelector('button[type="submit"]');
            var formData = new FormData(this);
            var original = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 导入中...';
            WMS.api.postRaw('/warehouse/import', formData, {headers: { 'X-Requested-With': 'XMLHttpRequest' }})
            .then(function(res) {
                btn.disabled = false;
                btn.innerHTML = original;
                if (res.status === 'success') {
                    notifyMasterDataChanged('warehouse_updated');
                    showToast(res.msg || '导入成功', 'success');
                    setTimeout(function(){ location.reload(); }, 1000);
                } else {
                    showToast(res.msg || '导入失败', 'danger', 3600);
                }
            })
            .catch(function(err) {
                btn.disabled = false;
                btn.innerHTML = original;
                showToast('导入失败: ' + err.message, 'danger', 3600);
            });
        });
    }
});

function submitAdd() {
    const form = document.getElementById('addForm');
    const formData = new FormData(form);

    WMS.api.postRaw('/warehouse/add', formData)
    .then(data => {
        if (data.status === 'success') {
            notifyMasterDataChanged('warehouse_updated');
            showToast('新增成功', 'success');
            setTimeout(() => location.reload(), 800);
        } else {
            showToast(data.msg || '新增失败', 'danger', 3600);
        }
    })
    .catch(err => showToast('新增失败：' + err.message, 'danger', 3600));
}

function editWarehouse(id) {
    return loadWmsMasterEditor('warehouse', id, function(w) {
        const form = document.getElementById('editForm');
        form.querySelector('[name="id"]').value = w.id;
        form.querySelector('[name="code"]').value = w.code;
        form.querySelector('[name="name"]').value = w.name;
        form.querySelector('[name="type"]').value = w.type || '';
        form.querySelector('[name="location"]').value = w.location || '';
        form.querySelector('[name="status"]').value = w.status;
        form.querySelector('[name="remark"]').value = w.remark || '';
        new bootstrap.Modal(document.getElementById('editModal')).show();
    });
}

function submitEdit() {
    if (isWmsMasterEditPending()) return;
    const form = document.getElementById('editForm');
    const formData = new FormData(form);
    const id = formData.get('id');

    WMS.api.postRaw('/warehouse/' + id + '/edit', formData)
    .then(data => {
        if (data.status === 'success') {
            notifyMasterDataChanged('warehouse_updated');
            showToast('编辑成功', 'success');
            setTimeout(() => location.reload(), 800);
        } else {
            showToast(data.msg || '编辑失败', 'danger', 3600);
        }
    })
    .catch(err => showToast('编辑失败：' + err.message, 'danger', 3600));
}

async function deleteWarehouse(id) {
    if (!(await showConfirm('确定要删除这个仓库吗？'))) return;

    WMS.api.postRaw('/warehouse/' + id + '/delete')
    .then(data => {
        if (data.status === 'success') {
            notifyMasterDataChanged('warehouse_updated');
            showToast('删除成功', 'success');
            setTimeout(() => location.reload(), 800);
        } else {
            showToast(data.msg || '删除失败', 'danger', 3600);
        }
    })
    .catch(err => showToast('删除失败：' + err.message, 'danger', 3600));
}

// M-03：设为默认仓
async function setDefaultWarehouse(id) {
    if (!(await showConfirm('确定将此仓库设为默认仓吗？同一时间仅一个默认仓。'))) return;
    WMS.api.postRaw('/warehouse/' + id + '/set_default', undefined, {headers: { 'X-Requested-With': 'XMLHttpRequest' }})
    .then(data => {
        if (data.status === 'success') {
            showToast(data.msg || '设置成功', 'success');
            setTimeout(() => location.reload(), 800);
        } else {
            showToast(data.msg || '设置失败', 'danger', 3600);
        }
    })
    .catch(err => showToast('设置失败：' + err.message, 'danger', 3600));
}

function notifyMasterDataChanged(type) {
    try {
        if (typeof BroadcastChannel !== 'undefined') {
            const bc = new BroadcastChannel('wms_master_data_update');
            bc.postMessage({type: type, timestamp: Date.now()});
            bc.close();
        }
    } catch(e) {}
}
