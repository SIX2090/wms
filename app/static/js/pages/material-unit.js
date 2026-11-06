const unitPageData = JSON.parse(document.getElementById('unit-page-data').textContent);

document.addEventListener('DOMContentLoaded', function() {
    initCheckAll('unitTable');

    // 新增单位
    var addForm = document.getElementById('addForm');
    if (addForm) {
        addForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var formData = new FormData(this);
            WMS.api.postRaw(unitPageData.add, formData)
            .then(function(res) {
                if (res.status === 'success') {
                    notifyMasterDataChanged('unit_updated');
                    showToast('单位已创建，正在刷新列表…', 'success');
                    setTimeout(function(){ location.reload(); }, 650);
                }
                else showToast(res.msg || '保存失败', 'danger', 3600);
            })
            .catch(function(err){ showToast('保存失败: ' + err.message, 'danger', 3600); });
        });
    }

    // 导入单位
    var importForm = document.getElementById('importForm');
    if (importForm) {
        importForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var formData = new FormData(this);
            WMS.api.postRaw(unitPageData.import, formData)
            .then(function(res) {
                if (res.status === 'success') {
                    notifyMasterDataChanged('unit_updated');
                    showToast(res.msg || '导入成功', 'success');
                    setTimeout(function(){ location.reload(); }, 650);
                } else {
                    showToast(res.msg, 'danger');
                }
            })
            .catch(function(err){ showToast('导入失败: ' + err.message, 'danger'); });
        });
    }

    // M-01：编辑单位
    var editForm = document.getElementById('editForm');
    if (editForm) {
        editForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (isWmsMasterEditPending()) return;
            var id = this.querySelector('[name="id"]').value;
            var formData = new FormData(this);
            WMS.api.postRaw('/unit/' + id + '/edit', formData)
            .then(function(res) {
                if (res.status === 'success') {
                    notifyMasterDataChanged('unit_updated');
                    showToast('编辑成功', 'success');
                    setTimeout(function(){ location.reload(); }, 650);
                } else {
                    showToast(res.msg || '编辑失败', 'danger', 3600);
                }
            })
            .catch(function(err){ showToast('编辑失败: ' + err.message, 'danger', 3600); });
        });
    }
});

// M-01：行级编辑 - 拉取单位详情并填充表单
function editUnit(id) {
    return loadWmsMasterEditor('unit', id, function(u) {
        var form = document.getElementById('editForm');
        form.querySelector('[name="id"]').value = u.id;
        form.querySelector('[name="code"]').value = u.code;
        form.querySelector('[name="name"]').value = u.name;
        new bootstrap.Modal(document.getElementById('editModal')).show();
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

document.addEventListener('click', function(event) {
    const edit = event.target.closest('[data-master-edit]');
    const remove = event.target.closest('[data-master-delete]');
    if (edit) { event.preventDefault(); window.editUnit(Number(edit.dataset.masterEdit)); }
    if (remove) { event.preventDefault(); deleteItem(unitPageData.delete, Number(remove.dataset.masterDelete)); }
});
document.addEventListener('keydown', function(event) {
    if (event.key === ' ' && event.target.matches('a[data-master-edit]')) {
        event.preventDefault(); event.target.click();
    }
});
