/* Repair task: AUDIT-FULL-20261016-001-F08. Writes use WMS.api and human confirmation. */
(function () {
    'use strict';
    document.addEventListener('DOMContentLoaded', function () {
        var table = document.getElementById('backup-history-table');
        if (!table || typeof setupResizableTable !== 'function') return;
        var keys = ['number', 'filename', 'source', 'created_at', 'size_bytes', 'integrity', 'actions'];
        table.querySelectorAll('thead th').forEach(function (header, index) { header.dataset.columnKey = keys[index]; });
        var storageKey = 'wms_backup_history_widths_v1';
        try {
            if (!localStorage.getItem(storageKey)) {
                var available = table.parentElement.clientWidth || 1100;
                localStorage.setItem(storageKey, JSON.stringify({widths: {
                    number: 48, filename: Math.max(260, available - 733), source: 170,
                    created_at: 155, size_bytes: 95, integrity: 90, actions: 175
                }, columnOrder: []}));
            }
        } catch (error) { return; }
        setupResizableTable({tableSelector: table, storageKey: storageKey, minWidth: 70, enableColumnReorder: false});
    });
    document.addEventListener('click', function (event) {
        var button = event.target.closest('button[data-backup-action]');
        if (!button || button.disabled) return;
        var action = button.dataset.backupAction;
        if (action === 'create' && !window.confirm('确认备份当前数据库？')) return;
        if (action === 'delete' && !window.confirm('确认删除备份“' + button.dataset.backupFilename + '”？')) return;
        var operation;
        var badge = button.closest('tr') && button.closest('tr').querySelector('[data-backup-check-status]');
        button.disabled = true;
        if (action === 'create') operation = WMS.api.post('/backup/create');
        else if (action === 'delete') operation = WMS.api.post('/backup/delete', {
            filename: button.dataset.backupFilename,
            source: button.dataset.backupSource
        });
        else if (action === 'verify') {
            if (badge) badge.textContent = '校验中…';
            operation = WMS.api.get(button.dataset.verifyUrl);
        } else { button.disabled = false; return; }
        operation.then(function (result) {
            if (action === 'verify') {
                if (badge) {
                    badge.textContent = result.valid === true ? '通过' : (result.valid === false ? '未通过' : '未完成');
                    badge.className = 'badge ' + (result.valid === true ? 'bg-success' : (result.valid === false ? 'bg-danger' : 'bg-secondary'));
                    badge.title = result.msg || '';
                }
                showToast(result.msg || '校验已完成', result.valid === true ? 'success' : 'warning');
            } else if (action === 'create') {
                var url = new URL(window.location.href);
                url.searchParams.delete('source');
                url.searchParams.delete('search');
                url.searchParams.set('sort', 'created_at');
                url.searchParams.set('order', 'desc');
                window.location.assign(url.pathname + url.search);
            } else window.location.reload();
        }).catch(function (error) {
            if (action === 'verify' && badge) badge.textContent = '未完成';
            showToast(error.message || '操作未完成，请重试', 'danger');
        }).finally(function () { button.disabled = false; });
    });
})();
