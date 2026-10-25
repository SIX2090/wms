document.addEventListener('DOMContentLoaded', function() {
    initCheckAll('departmentTable');

    // 导入部门
    var importForm = document.getElementById('importForm');
    if (importForm) {
        importForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var btn = this.querySelector('button[type="submit"]');
            var formData = new FormData(this);
            var original = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 导入中...';
            WMS.api.postRaw('/department/import', formData, {headers: { 'X-Requested-With': 'XMLHttpRequest' }})
            .then(function(res) {
                btn.disabled = false;
                btn.innerHTML = original;
                if (res.status === 'success') {
                    notifyMasterDataChanged('department_updated');
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

    WMS.api.postRaw('/department/add', formData)
    .then(data => {
        if (data.status === 'success') {
            notifyMasterDataChanged('department_updated');
            showToast('新增成功', 'success');
            setTimeout(() => location.reload(), 800);
        } else {
            showToast(data.msg || '新增失败', 'danger', 3600);
        }
    })
    .catch(err => showToast('新增失败：' + err.message, 'danger', 3600));
}

function editDepartment(id) {
    return loadWmsMasterEditor('department', id, function(d) {
        const form = document.getElementById('editForm');
        form.querySelector('[name="id"]').value = d.id;
        form.querySelector('[name="code"]').value = d.code;
        form.querySelector('[name="name"]').value = d.name;
        form.querySelector('[name="status"]').value = d.status;
        form.querySelector('[name="remark"]').value = d.remark || '';
        new bootstrap.Modal(document.getElementById('editModal')).show();
    });
}

function submitEdit() {
    if (isWmsMasterEditPending()) return;
    const form = document.getElementById('editForm');
    const formData = new FormData(form);
    const id = formData.get('id');

    WMS.api.postRaw('/department/' + id + '/edit', formData)
    .then(data => {
        if (data.status === 'success') {
            notifyMasterDataChanged('department_updated');
            showToast('编辑成功', 'success');
            setTimeout(() => location.reload(), 800);
        } else {
            showToast(data.msg || '编辑失败', 'danger', 3600);
        }
    })
    .catch(err => showToast('编辑失败：' + err.message, 'danger', 3600));
}

async function deleteDepartment(id) {
    if (!(await showConfirm('确定要删除这个部门吗？'))) return;

    WMS.api.postRaw('/department/' + id + '/delete')
    .then(data => {
        if (data.status === 'success') {
            notifyMasterDataChanged('department_updated');
            showToast('删除成功', 'success');
            setTimeout(() => location.reload(), 800);
        } else {
            showToast(data.msg || '删除失败', 'danger', 3600);
        }
    })
    .catch(err => showToast('删除失败：' + err.message, 'danger', 3600));
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
