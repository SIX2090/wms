const categoryPageData = JSON.parse(document.getElementById('category-page-data').textContent);

document.addEventListener('DOMContentLoaded', function() {
    initCheckAll('categoryTable');

    // 新增分类
    var addForm = document.getElementById('addForm');
    if (addForm) {
        addForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var formData = new FormData(this);
            WMS.api.postRaw(categoryPageData.add, formData)
            .then(function(res) {
                if (res.status === 'success') {
                    notifyMasterDataChanged('category_updated');
                    location.reload();
                }
                else showToast(res.msg, 'danger');
            })
            .catch(function(err){ showToast('保存失败: ' + err.message, 'danger'); });
        });
    }

    // 编辑分类
    window.editCategory = function(id) {
        return loadWmsMasterEditor('category', id, function(cat) {
            document.getElementById('editId').value = cat.id;
            document.getElementById('editCode').value = cat.code;
            document.getElementById('editName').value = cat.name;
            var parentSelect = document.getElementById('editParentId');
            parentSelect.value = cat.parent_id || '';
            Array.from(parentSelect.options).forEach(function(option) {
                option.disabled = option.value === String(cat.id);
            });
            var editModal = new bootstrap.Modal(document.getElementById('editModal'));
            editModal.show();
        });
    };

    var editForm = document.getElementById('editForm');
    if (editForm) {
        editForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (isWmsMasterEditPending()) return;
            var id = document.getElementById('editId').value;
            var formData = new FormData(this);
            WMS.api.postRaw('/category/edit/' + id, formData)
            .then(function(res) {
                if (res.status === 'success') {
                    notifyMasterDataChanged('category_updated');
                    location.reload();
                }
                else showToast(res.msg, 'danger');
            })
            .catch(function(err){ showToast('保存失败: ' + err.message, 'danger'); });
        });
    }

    // 导入分类
    var importForm = document.getElementById('importForm');
    if (importForm) {
        importForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var formData = new FormData(this);
            WMS.api.postRaw(categoryPageData.import, formData)
            .then(function(res) {
                if (res.status === 'success') {
                    notifyMasterDataChanged('category_updated');
                    showToast(res.msg || '导入成功', 'success');
                    setTimeout(function(){ location.reload(); }, 650);
                } else {
                    showToast(res.msg, 'danger');
                }
            })
            .catch(function(err){ showToast('导入失败: ' + err.message, 'danger'); });
        });
    }
});

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
    if (edit) { event.preventDefault(); window.editCategory(Number(edit.dataset.masterEdit)); }
    if (remove) { event.preventDefault(); deleteItem(categoryPageData.delete, Number(remove.dataset.masterDelete)); }
});
document.addEventListener('keydown', function(event) {
    if (event.key === ' ' && event.target.matches('a[data-master-edit]')) {
        event.preventDefault(); event.target.click();
    }
});
