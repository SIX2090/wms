/* Paste an Excel material-code column into editable requisition rows. */
(function(global) {
    'use strict';

    global.WMS.bindMaterialCodePaste = function(options) {
        const body = document.getElementById(options.bodyId);
        if (!body) return;
        let busy = false, revision = 0;
        document.addEventListener('input', () => { revision++; });
        document.addEventListener('change', () => { revision++; });
        const empty = row => Array.from(row.querySelectorAll('input, select, textarea')).every(
            field => field.readOnly || field.disabled || !String(field.value || '').trim());

        body.addEventListener('paste', async function(event) {
            const input = event.target;
            if (!input.classList.contains('material-code') || input.readOnly || input.disabled) return;
            const text = event.clipboardData && event.clipboardData.getData('text/plain');
            if (!text) return;
            event.preventDefault();
            if (!options.enabled()) return;
            if (busy) { showToast('正在查询物料，请稍候再粘贴', 'info'); return; }
            const startRow = input.closest('tr');
            if (!startRow || !body.contains(startRow) || !empty(startRow)) {
                showToast('请在空白明细行的物料编码格粘贴，保留已有明细', 'warning'); return;
            }
            const warehouse = global.WMS.materialCache.warehouseFromForm();
            if (!warehouse || global.WMS.materialCache.isRefreshing(options.materials)) {
                showToast('请先选择仓库并等待库存刷新完成，再粘贴', 'warning'); return;
            }

            const entries = [];
            for (const [index, line] of text.replace(/^\uFEFF/, '').split(/\r\n?|\n/).entries()) {
                const cells = line.split('\t').map(value => value.trim());
                if (cells.every(value => !value)) continue;
                if (cells.slice(1).some(Boolean)) {
                    showToast('请只复制物料编码这一列；带数量等多列数据请使用粘贴导入', 'warning'); return;
                }
                const code = cells[0];
                if (!entries.length && ['物料编码', '物料代码'].includes(code)) continue;
                if (!code || code.length > 100) {
                    showToast('第' + (index + 1) + '行物料编码无效，最多100个字符', 'warning'); return;
                }
                entries.push({code, line: index + 1});
            }
            if (!entries.length) { showToast('请复制物料编码内容后再粘贴', 'warning'); return; }

            const ticket = revision;
            const current = () => body.isConnected && body.contains(startRow) && startRow.isConnected &&
                revision === ticket && options.enabled() && empty(startRow) &&
                warehouse === global.WMS.materialCache.warehouseFromForm() &&
                !global.WMS.materialCache.isRefreshing(options.materials);
            busy = true;
            try {
                // Recheck every code on the existing active-material, warehouse-scoped endpoint.
                // 200 is an API batch size, not a limit on the pasted column.
                const codes = [...new Set(entries.map(entry => entry.code))], found = new Map();
                for (let offset = 0; offset < codes.length; offset += 200) {
                    const params = new URLSearchParams();
                    codes.slice(offset, offset + 200).forEach(code => params.append('code', code));
                    params.set('warehouse', warehouse);
                    const materials = await global.WMS.api.get('/material/api/by_codes?' + params.toString());
                    if (!current()) throw new Error('页面内容或仓库已变化，请核对后重新粘贴');
                    if (!Array.isArray(materials)) throw new Error('物料查询结果无效，请重试');
                    materials.forEach(material => {
                        if (material && typeof material.code === 'string') found.set(material.code, material);
                    });
                }
                const missing = entries.filter(entry => !found.has(entry.code));
                if (missing.length) {
                    throw new Error('物料不存在或已停用：' + missing.slice(0, 5).map(
                        entry => '第' + entry.line + '行 ' + entry.code).join('、') +
                        (missing.length > 5 ? '等，共' + missing.length + '行' : ''));
                }
                // Validate the whole lookup before modifying rows or the shared candidate cache.
                found.forEach(material => {
                    const index = options.materials.findIndex(item => item.code === material.code);
                    if (index < 0) options.materials.push(material);
                    else options.materials[index] = material;
                });
                let row = startRow;
                for (const [index, entry] of entries.entries()) {
                    if (index) {
                        const next = row.nextElementSibling;
                        if (next && empty(next)) row = next;
                        else {
                            row = options.createRow();
                            if (next) body.insertBefore(row, next);
                        }
                    }
                    row.querySelector(options.quantitySelector).value = '';
                    options.fillRow(row, found.get(entry.code));
                }
                options.renumberRows();
                startRow.querySelector(options.quantitySelector).focus();
                showToast('已填入 ' + entries.length + ' 行物料，请填写领料数量后保存', 'success');
            } catch (error) {
                showToast('编码粘贴未完成：' + error.message, 'danger');
            } finally {
                busy = false;
            }
        });
    };
})(window);
