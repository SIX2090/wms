function openSalesBatchDialog(body, recalc) {
    const dialog = document.getElementById('salesBatchDialog');
    const form = dialog.querySelector('form');
    const field = form.querySelector('select');
    const value = form.querySelector('input');
    const apply = form.querySelector('[type="submit"]');
    const preview = document.getElementById('salesBatchPreview');
    const rows = Array.from(body.rows).filter(row => row.querySelector('.material-code').value.trim());

    function newValue() {
        return field.value === 'tax-rate' ? value.valueAsNumber / 100 : value.valueAsNumber;
    }

    function changedInputs() {
        return rows.map(row => row.querySelector('.' + field.value)).filter(input =>
            !input.disabled && !input.readOnly && (input.value === '' || input.valueAsNumber !== newValue()));
    }

    function updatePreview() {
        const valid = value.validity.valid;
        const count = valid ? changedInputs().length : 0;
        apply.disabled = !count;
        if (!rows.length) preview.textContent = '请先填写物料编码。';
        else if (!valid) preview.textContent = '已填写物料 ' + rows.length + ' 行。' + value.validationMessage;
        else preview.textContent = '已填写物料 ' + rows.length + ' 行，本次将修改 ' + count + ' 行。';
    }

    function resetValue() {
        value.value = '';
        value.min = field.value === 'qty' ? '0.01' : '0';
        value.step = field.value === 'tax-rate' ? '1' : '0.01';
        if (field.value === 'tax-rate') value.max = '100';
        else value.removeAttribute('max');
        updatePreview();
    }

    field.value = 'price';
    resetValue();
    field.onchange = resetValue;
    value.oninput = updatePreview;
    form.querySelector('[data-cancel]').onclick = () => dialog.close();
    form.onsubmit = event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const inputs = changedInputs();
        if (!inputs.length) return;
        inputs.forEach(input => { input.value = String(newValue()); });
        recalc();
        document.getElementById('entryStatus').textContent = '已修改 ' + inputs.length + ' 行，请核对后保存。';
        dialog.close();
    };
    dialog.showModal();
}
