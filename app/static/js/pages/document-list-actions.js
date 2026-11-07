// Fixed event bindings for the three migrated document lists.
(function() {
    'use strict';
    function orderId(node) {
        var id = node.getAttribute('data-order-id') || '';
        return /^[1-9]\d*$/.test(id) ? id : null;
    }
    var actions = {
        "in-order-batch-complete": function(node) { batchInOrderAction('/in_order/batch_complete', '请选择要完成的入库单', '确认完成选中的入库单？完成后会增加库存。'); },
        "in-order-batch-print": function(node) { batchInOrderAction('/in_order/batch_print', '请选择要打印的入库单', '确认打印选中的入库单？'); },
        "in-order-batch-export": function(node) { batchInOrderAction('/in_order/batch_export', '请选择要导出的入库单', '确认导出选中的入库单？'); },
        "in-order-choose-import": function(node) { document.getElementById('inOrderImportFile').click(); },
        "in-order-batch-delete": function(node) { batchInOrderAction('/in_order/batch_delete', '请选择要删除的入库单', '确认删除选中的入库单？'); },
        "in-order-copyInOrder": function(node) { var id = orderId(node); if (id) copyInOrder(id); },
        "out-order-batch-delete": function(node) { batchOutOrderAction('/out_order/batch_delete', '请选择要删除的' + outOrderBusinessLabel(), '确认删除选中的' + outOrderBusinessLabel() + '？'); },
        "out-order-batch-complete": function(node) { batchOutOrderAction('/out_order/batch_complete', '请选择要完成的' + outOrderBusinessLabel(), '确认完成选中的' + outOrderBusinessLabel() + '？完成后会扣减库存。'); },
        "out-order-choose-import": function(node) { document.getElementById('outOrderImportFile').click(); },
        "out-order-complete": function(node) { var id = orderId(node); if (id) singleOutOrderAction('/out_order/' + id + '/complete', '确认完成该' + outOrderBusinessLabel() + '？完成后会扣减库存。'); },
        "out-order-delete": function(node) { var id = orderId(node); if (id) singleOutOrderAction('/out_order/' + id + '/delete', '确认删除该' + outOrderBusinessLabel() + '？'); },
        "out-order-revert": function(node) { var id = orderId(node); if (id) singleOutOrderAction('/out_order/' + id + '/revert', '确认反提交该' + outOrderBusinessLabel() + '？反提交后库存将恢复。'); },
        "after-sale-out-choose-import": function(node) { document.getElementById('afterSaleOutImportFile').click(); },
        "after-sale-out-print": function(node) { printAfterSaleOutList(); },
        "after-sale-out-completeOrder": function(node) { var id = orderId(node); if (id) completeOrder(id); },
        "after-sale-out-deleteOrder": function(node) { var id = orderId(node); if (id) deleteOrder(id); },
        "after-sale-out-revertOrder": function(node) { var id = orderId(node); if (id) revertOrder(id); }
    };
    document.addEventListener('click', function(event) {
        if (!event.target.closest) return;
        var node = event.target.closest('[data-document-list-action]');
        if (!node || node.disabled) return;
        var name = node.getAttribute('data-document-list-action');
        if (!Object.prototype.hasOwnProperty.call(actions, name)) return;
        event.preventDefault();
        actions[name](node);
    });
    document.addEventListener('change', function(event) {
        var node = event.target;
        var action = node.getAttribute && node.getAttribute('data-document-list-change');
        if (action === 'page-size') changePerPage(node.value);
        else if (action === 'import' && node.form) submitDocumentImport(node.form.id, node.id);
        else if (action === 'select-all') toggleAll();
    });
    document.addEventListener('DOMContentLoaded', function() {
        // flatpickr hides the original date input; point its label at the usable one.
        document.querySelectorAll('input[id]').forEach(function(input) {
            var visible = input._flatpickr && input._flatpickr.altInput;
            if (!visible) return;
            var label = document.querySelector('label[for="' + input.id + '"]');
            if (!label) return;
            visible.id = input.id + 'Display';
            visible.setAttribute('aria-label', label.textContent.trim());
            label.htmlFor = visible.id;
        });
    });
})();
