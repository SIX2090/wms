// Reuse the BOM draft endpoint; completion and stock changes remain manual.
async function submitBomRequisition(event) {
    event.preventDefault();
    const form = document.getElementById('bomRequisitionForm');
    const button = document.getElementById('bomRequisitionSubmit');
    if (button.disabled || !form.reportValidity()) return;
    const bomId = document.getElementById('bomRequisitionId').value;
    if (!/^[1-9]\d*$/.test(bomId)) {
        showToast('请从候选列表选择BOM', 'warning');
        return;
    }
    const warehouseId = Number(document.getElementById('bomRequisitionWarehouse').value);
    if (!Number.isInteger(warehouseId) || warehouseId <= 0) {
        showToast('请选择领料仓库', 'warning');
        return;
    }
    const location = document.getElementById('bomRequisitionLocation');
    button.disabled = true;
    try {
        const result = await WMS.api.post('/bom/' + bomId + '/create_requisition', {
            warehouse_id: warehouseId, location: location ? location.value.trim() : ''
        });
        if (!result.id) throw new Error('未返回领料草稿编号，请刷新列表确认');
        window.location.href = '/requisition/' + encodeURIComponent(result.id) +
            (new URLSearchParams(window.location.search).get('embedded') === '1' ? '?embedded=1' : '');
    } catch (error) {
        showToast(error.message || '生成失败，请稍后重试', 'danger');
    } finally {
        button.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const button = document.getElementById('openBomRequisition');
    const bar = document.getElementById('cbGlobalActionBar');
    if (button && bar) bar.insertBefore(button, bar.children[1] || null);
    const form = document.getElementById('bomRequisitionForm');
    if (!form) return;
    form.addEventListener('submit', submitBomRequisition);
    document.getElementById('bomRequisitionSearch').addEventListener('input', function() {
        document.getElementById('bomRequisitionId').value = '';
    });
    document.getElementById('bomRequisitionModal').addEventListener('show.bs.modal', function() {
        form.reset();
        document.getElementById('bomRequisitionId').value = '';
    });
});
