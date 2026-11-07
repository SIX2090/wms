/* Names and focus for the explicitly opted-in document forms and their dialogs. */
(function () {
    'use strict';
    let nextId = 0;
    let activeDialog = null;
    let lastOutsideFocus = null;
    let pending = false;
    const dialogOpeners = new WeakMap();
    const controls = 'input:not([type="hidden"]),select,textarea';

    function controlId(control) {
        if (control.id) return control.id;
        let id;
        do { id = 'wms-document-field-' + (++nextId); } while (document.getElementById(id));
        control.id = id;
        return id;
    }

    function labelControl(label) {
        // Flatpickr keeps the submitted value in a hidden input; focus its visible clone.
        const original = label.htmlFor ? document.getElementById(label.htmlFor) :
            label.parentElement.querySelector(controls + ',input.flatpickr-input');
        if (!original) return;
        const control = original._flatpickr && original._flatpickr.altInput || original;
        if (control.type === 'hidden') return;
        label.htmlFor = controlId(control);
    }

    function nameRows(table) {
        const headers = Array.from(table.querySelectorAll('thead th'));
        table.querySelectorAll('tbody tr').forEach(function (row, index) {
            Array.from(row.cells).forEach(function (cell) {
                const header = headers.find(function (th) {
                    return cell.dataset.columnKey && th.dataset.columnKey === cell.dataset.columnKey;
                }) || headers[cell.cellIndex];
                if (!header) return;
                // Use today's displayed column name, including the saved field settings.
                const title = Array.from(header.childNodes).filter(function (node) {
                    return node.nodeType === 3;
                }).map(function (node) { return node.textContent; }).join('').trim() || header.dataset.defaultLabel;
                if (!title) return;
                cell.querySelectorAll(controls).forEach(function (control) {
                    if (control.hasAttribute('aria-labelledby') ||
                        (control.hasAttribute('aria-label') && !control.dataset.wmsRowName)) return;
                    const name = '第' + (index + 1) + '行 ' + title;
                    if (control.getAttribute('aria-label') !== name) control.setAttribute('aria-label', name);
                    control.dataset.wmsRowName = 'true';
                });
            });
        });
    }

    function dialogControls(dialog) {
        return Array.from(dialog.querySelectorAll('button,input,select,textarea,a[href],[tabindex]'))
            .filter(function (control) {
                return !control.disabled && control.tabIndex >= 0 && control.getClientRects().length;
            });
    }

    function returnFocus(dialog) {
        const opener = dialogOpeners.get(dialog);
        dialogOpeners.delete(dialog);
        if (activeDialog === dialog) activeDialog = null;
        if (opener && opener.isConnected && !opener.disabled) opener.focus();
    }

    function openPasteDialog(dialog) {
        dialogOpeners.set(dialog, document.activeElement === document.body ? lastOutsideFocus : document.activeElement);
        activeDialog = dialog;
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        const title = dialog.querySelector('h5');
        if (title) dialog.setAttribute('aria-labelledby', controlId(title));
        const input = dialog.querySelector('textarea');
        if (input) {
            input.setAttribute('aria-label', '粘贴导入内容');
            input.focus();
        } else if (dialogControls(dialog)[0]) dialogControls(dialog)[0].focus();
    }

    function refresh() {
        pending = false;
        document.querySelectorAll('form label').forEach(labelControl);
        document.querySelectorAll('table').forEach(nameRows);
        if (activeDialog && !activeDialog.isConnected) returnFocus(activeDialog);
        const confirmation = document.getElementById('completeConfirmModal');
        if (confirmation && activeDialog !== confirmation) openPasteDialog(confirmation);
    }

    function scheduleRefresh() {
        if (!pending) {
            pending = true;
            window.requestAnimationFrame(refresh);
        }
    }

    document.addEventListener('keydown', function (event) {
        if (!activeDialog || !activeDialog.isConnected) return;
        const dialog = activeDialog;
        if (event.key === 'Escape') {
            event.preventDefault();
            event.stopImmediatePropagation();
            dialog.remove();
            returnFocus(dialog);
        } else if (event.key === 'Tab') {
            const items = dialogControls(dialog);
            const first = items[0], last = items[items.length - 1];
            if (first && (!dialog.contains(document.activeElement) ||
                (event.shiftKey ? document.activeElement === first : document.activeElement === last))) {
                event.preventDefault();
                (event.shiftKey ? last : first).focus();
            }
        }
    }, true);
    document.addEventListener('focusin', function (event) {
        if (activeDialog && activeDialog.isConnected && !activeDialog.contains(event.target)) {
            const first = dialogControls(activeDialog)[0];
            if (first) first.focus();
        } else if (!activeDialog && event.target !== document.body) lastOutsideFocus = event.target;
    });
    document.addEventListener('show.bs.modal', function (event) {
        dialogOpeners.set(event.target, event.relatedTarget || document.activeElement);
    });
    document.addEventListener('shown.bs.modal', function (event) {
        refresh();
        const input = dialogControls(event.target).find(function (item) {
            return item.matches('input:not([readonly]),select,textarea:not([readonly])');
        });
        if (input) input.focus();
    });
    document.addEventListener('hidden.bs.modal', function (event) { returnFocus(event.target); });

    window.WmsFormAccessibility = {openPasteDialog: openPasteDialog};
    function initialize() {
        refresh();
        new MutationObserver(scheduleRefresh).observe(document.body, {
            childList: true, subtree: true, characterData: true,
            attributes: true, attributeFilter: ['class', 'hidden']
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
    else initialize();
})();
