document.addEventListener('DOMContentLoaded', function() {
    initCheckAll('employeeTable');
});

function showAddModal() {
    var form = document.getElementById('addForm');
    if (form) form.reset();
    new bootstrap.Modal(document.getElementById('addModal')).show();
}

function submitAdd() {
    var form = document.getElementById('addForm');
    var formData = new FormData(form);
    WMS.api.postRaw('/employee/add', formData)
    .then(function(data) {
        if (data.status === 'success') {
            notifyMasterDataChanged('employee_updated');
            showToast('新增成功', 'success');
            setTimeout(function(){ location.reload(); }, 800);
        } else {
            showToast(data.msg || '新增失败', 'danger', 3600);
        }
    })
    .catch(function(err){ showToast('新增失败：' + err.message, 'danger', 3600); });
}

function editEmployee(id) {
    WMS.api.getRaw('/employee/' + id)
    .then(function(data) {
        if (data.status === 'success') {
            var e = data.employee;
            var form = document.getElementById('editForm');
            form.querySelector('[name="id"]').value = e.id;
            form.querySelector('[name="code"]').value = e.code;
            form.querySelector('[name="name"]').value = e.name;
            form.querySelector('[name="position"]').value = e.position;
            form.querySelector('[name="phone"]').value = e.phone;
            form.querySelector('[name="department_id"]').value = e.department_id || '';
            new bootstrap.Modal(document.getElementById('editModal')).show();
        } else {
            showToast(data.msg || '获取数据失败', 'danger', 3600);
        }
    })
    .catch(function(err){ showToast('获取数据失败：' + err.message, 'danger', 3600); });
}

function submitEdit() {
    var form = document.getElementById('editForm');
    var formData = new FormData(form);
    var id = formData.get('id');
    WMS.api.postRaw('/employee/' + id + '/edit', formData)
    .then(function(data) {
        if (data.status === 'success') {
            notifyMasterDataChanged('employee_updated');
            showToast('编辑成功', 'success');
            setTimeout(function(){ location.reload(); }, 800);
        } else {
            showToast(data.msg || '编辑失败', 'danger', 3600);
        }
    })
    .catch(function(err){ showToast('编辑失败：' + err.message, 'danger', 3600); });
}

async function deleteEmployee(id) {
    if (!(await showConfirm('确定要删除这个员工吗？'))) return;
    WMS.api.postRaw('/employee/delete', {ids: [id]}, {headers: {'Content-Type': 'application/json'}})
    .then(function(data) {
        if (data.status === 'success') {
            notifyMasterDataChanged('employee_updated');
            showToast('删除成功', 'success');
            setTimeout(function(){ location.reload(); }, 800);
        } else {
            showToast(data.msg || '删除失败', 'danger', 3600);
        }
    })
    .catch(function(err){ showToast('删除失败：' + err.message, 'danger', 3600); });
}

async function batchDelete() {
    var ids = Array.from(document.querySelectorAll('.check-item:checked')).map(function(el){ return el.value; });
    if (!ids.length) {
        showToast('请先勾选要删除的员工', 'warning', 2400);
        return;
    }
    if (!(await showConfirm('确定要删除选中的 ' + ids.length + ' 条员工吗？'))) return;
    WMS.api.postRaw('/employee/delete', {ids: ids}, {headers: {'Content-Type': 'application/json'}})
    .then(function(data) {
        if (data.status === 'success') {
            notifyMasterDataChanged('employee_updated');
            showToast('删除成功', 'success');
            setTimeout(function(){ location.reload(); }, 800);
        } else {
            showToast(data.msg || '删除失败', 'danger', 3600);
        }
    })
    .catch(function(err){ showToast('删除失败：' + err.message, 'danger', 3600); });
}

function showImportModal() {
    var form = document.getElementById('importForm');
    if (form) form.reset();
    var result = document.querySelector('#importModal .import-result');
    if (result) result.innerHTML = '';
    new bootstrap.Modal(document.getElementById('importModal')).show();
}

function submitImport() {
    var form = document.getElementById('importForm');
    var formData = new FormData(form);
    var result = document.querySelector('#importModal .import-result');
    result.innerHTML = '<span class="text-muted">导入中...</span>';
    WMS.api.postRaw('/employee/import', formData, {headers: { 'X-Requested-With': 'XMLHttpRequest' }})
    .then(function(data) {
        if (data.status === 'success') {
            result.innerHTML = '<div class="alert alert-success py-1 mb-0"><i class="bi bi-check-circle"></i> ' + escapeHtml(data.msg) + '</div>';
            setTimeout(function(){ location.reload(); }, 1200);
        } else {
            result.innerHTML = '<div class="alert alert-danger py-1 mb-0"><i class="bi bi-x-circle"></i> ' + escapeHtml(data.msg || '导入失败') + '</div>';
        }
    })
    .catch(function(err){
        result.innerHTML = '<div class="alert alert-danger py-1 mb-0"><i class="bi bi-x-circle"></i> 请求失败：' + escapeHtml(err.message) + '</div>';
    });
}

function notifyMasterDataChanged(type) {
    try {
        if (typeof BroadcastChannel !== 'undefined') {
            var bc = new BroadcastChannel('wms_master_data_update');
            bc.postMessage({type: type, timestamp: Date.now()});
            bc.close();
        }
    } catch(e) {}
}
