/* Product receipt clipboard entry. Masters are resolved only by the save endpoint. */
(function (root) {
    'use strict';
    const fields = [
        ['material_code', '.material-code', '物料编码', 50],
        ['box_no', '.material-box-no', '箱体编号', 100],
        ['material_name', '.material-name', '物料名称', 100],
        ['spec', '.material-spec', '规格', 100],
        ['unit', '.material-unit', '单位', 20],
        ['quantity', '.material-qty', '数量'],
        ['price', '.material-price', '单价'],
        ['batch_no', '.material-batch-no', '批次号', 50],
        ['expiry_date', '.material-expiry', '有效期'],
        ['contract_no', '.line-contract-no', '合同编号', 50],
        ['project_name', '.line-project-name', '工程名称', 200],
        ['remark', '.material-remark', '备注', 500]
    ];
    const fiveColumns = ['box_no', 'material_name', 'spec', 'unit', 'quantity'];

    function parseTsv(text) {
        const rows = [];
        let row = [], cell = '', quoted = false;
        const input = String(text).replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n');
        for (let index = 0; index < input.length; index++) {
            const ch = input[index];
            if (ch === '"' && (quoted || cell === '')) {
                if (quoted && input[index + 1] === '"') { cell += '"'; index++; }
                else quoted = !quoted;
            } else if (!quoted && (ch === '\t' || ch === '\n')) {
                row.push(cell);
                cell = '';
                if (ch === '\n') { rows.push(row); row = []; }
            } else cell += ch;
        }
        if (quoted) throw new Error('单元格引号未闭合，请重新从 Excel 复制');
        row.push(cell);
        rows.push(row);
        while (rows.length && rows[rows.length - 1].every(value => value === '')) rows.pop();
        if (!rows.length) throw new Error('请先复制需要粘贴的单元格');
        if (rows.length > 1000) throw new Error('一次最多粘贴 1000 行，请分批粘贴');
        return rows;
    }

    function planPaste(text, columns, startKey) {
        let rows = parseTsv(text);
        const start = columns.indexOf(startKey);
        if (start < 0) throw new Error('请选择可填写的单元格');
        const isFive = startKey === 'box_no' && rows.every(row => row.length === 5);
        const targets = isFive ? fiveColumns : columns.slice(start);
        if (isFive && rows[0][0].trim() === '箱体编号' && /名称/.test(rows[0][1])) rows = rows.slice(1);
        return rows.map((row, index) => {
            if (row.length > targets.length) throw new Error('第 ' + (index + 1) + ' 行超出可填写列，未粘贴');
            const patch = {};
            row.forEach((raw, column) => {
                const key = targets[column];
                const definition = fields.find(field => field[0] === key);
                const value = raw.trim();
                if (definition[3] && value.length > definition[3]) throw new Error('第 ' + (index + 1) + ' 行' + definition[2] + '超过' + definition[3] + '字符');
                if (value && (key === 'quantity' || key === 'price')) {
                    if (!/^(?:\d+(?:\.\d{1,2})?|\.\d{1,2})$/.test(value) || !Number.isFinite(Number(value)) ||
                        (key === 'quantity' && Number(value) <= 0)) {
                        throw new Error('第 ' + (index + 1) + ' 行' + definition[2] + '须为有效数字，最多两位小数；数量须大于0');
                    }
                }
                if (value && key === 'expiry_date') {
                    const date = new Date(value + 'T00:00:00Z');
                    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) {
                        throw new Error('有效期请使用有效的 YYYY-MM-DD 日期');
                    }
                }
                patch[key] = value;
            });
            return patch;
        });
    }

    function toTsv(rows) {
        return rows.map(row => row.map(value => /[\t\n\r"]/.test(value)
            ? '"' + value.replace(/"/g, '""') + '"' : value).join('\t')).join('\r\n');
    }

    function init(options) {
        const table = document.getElementById('materialTable');
        if (!table || table.dataset.productClipboard) return;
        table.dataset.productClipboard = '1';
        const body = table.tBodies[0];
        let anchor = null, selection = [];
        const inputFor = (row, key) => row.querySelector(fields.find(field => field[0] === key)[1]);
        const columnsFor = row => Array.from(row.cells).map(cell => cell.dataset.columnKey)
            .filter(key => fields.some(field => field[0] === key) && inputFor(row, key) &&
                !row.querySelector('[data-column-key="' + key + '"]').hidden &&
                getComputedStyle(row.querySelector('[data-column-key="' + key + '"]')).display !== 'none');
        const used = row => fields.some(field => row.querySelector(field[1])?.value.trim());
        function select(cells) {
            table.querySelectorAll('.product-grid-selected').forEach(cell => cell.classList.remove('product-grid-selected'));
            selection = cells;
            cells.forEach(cell => cell.classList.add('product-grid-selected'));
        }
        function paste(text, row, key, explicitColumns) {
            try {
                const patches = planPaste(text, explicitColumns || columnsFor(row), key);
                const offset = Array.from(body.rows).indexOf(row);
                if (offset + patches.length > 1000) throw new Error('单据最多粘贴到 1000 行，请分单录入');
                // Parse and validate the entire block before changing any cell.
                patches.forEach((patch, index) => {
                    while (body.rows.length <= offset + index) options.addRow();
                    const target = body.rows[offset + index];
                    if (patch.material_code) options.fillCode(target, patch.material_code);
                    Object.entries(patch).forEach(([field, value]) => { inputFor(target, field).value = value; });
                    const price = inputFor(target, 'price');
                    if (!price.value) price.value = '0';
                    if (Object.keys(patch).some(field => ['material_code', 'material_name', 'spec', 'unit'].includes(field))) {
                        target.dataset.sourcePurchaseOrderItemId = '';
                        target.dataset.sourcePurchaseOrderNo = '';
                    }
                    options.calculate(target);
                    target.querySelector('.material-qty').dispatchEvent(new Event('input', {bubbles: true}));
                });
                document.getElementById('addForm').dataset.modified = 'true';
                options.calculate(row);
                showToast('已粘贴 ' + patches.length + ' 行；保存时匹配物料并为新物料编号', 'success');
                return true;
            } catch (error) {
                showToast(error.message, 'warning');
                return false;
            }
        }
        table.addEventListener('pointerdown', event => {
            const cell = event.target.closest('td, th');
            if (!cell || event.target.closest('button, .col-resize, .resize-handle')) return;
            const row = cell.closest('tr'), key = cell.dataset.columnKey;
            const rows = Array.from(body.rows);
            if (cell.tagName === 'TH' && fields.some(field => field[0] === key)) {
                const last = rows.reduce((result, candidate, index) => used(candidate) ? index : result, 0);
                anchor = rows[0]?.querySelector('[data-column-key="' + key + '"]');
                select(rows.slice(0, last + 1).map(candidate => candidate.querySelector('[data-column-key="' + key + '"]')));
                inputFor(rows[0], key).focus();
            } else if (body.contains(row) && key === 'row_no') {
                anchor = row.querySelector('[data-column-key="' + columnsFor(row)[0] + '"]');
                select(columnsFor(row).map(field => row.querySelector('[data-column-key="' + field + '"]')));
                inputFor(row, columnsFor(row)[0]).focus();
            } else if (body.contains(row) && fields.some(field => field[0] === key)) {
                if (event.shiftKey && anchor && body.contains(anchor)) {
                    event.preventDefault();
                    const columns = columnsFor(row);
                    const ends = [columns.indexOf(anchor.dataset.columnKey), columns.indexOf(key)].sort((a,b) => a-b);
                    const rowEnds = [rows.indexOf(anchor.closest('tr')), rows.indexOf(row)].sort((a,b) => a-b);
                    select(rows.slice(rowEnds[0], rowEnds[1] + 1).flatMap(candidate => columns.slice(ends[0], ends[1] + 1)
                        .map(field => candidate.querySelector('[data-column-key="' + field + '"]'))));
                } else { anchor = cell; select([cell]); }
            }
        });
        table.addEventListener('copy', event => {
            if (!selection.length || !event.clipboardData) return;
            if (selection.length === 1 && event.target.selectionEnd > event.target.selectionStart) return;
            const selectedRows = [];
            selection.forEach(cell => {
                const row = cell.closest('tr');
                let selected = selectedRows.find(entry => entry.row === row);
                if (!selected) { selected = {row, values: []}; selectedRows.push(selected); }
                selected.values.push(inputFor(row, cell.dataset.columnKey).value);
            });
            event.clipboardData.setData('text/plain', toTsv(selectedRows.map(entry => entry.values)));
            event.preventDefault();
        });
        table.addEventListener('focusin', event => {
            const cell = event.target.closest('td');
            if (cell && fields.some(field => field[0] === cell.dataset.columnKey) && !selection.includes(cell)) {
                anchor = cell;
                select([cell]);
            }
        });
        table.addEventListener('paste', event => {
            const input = event.target.closest('input');
            const cell = input?.closest('td');
            if (!cell || !fields.some(field => field[0] === cell.dataset.columnKey) || !event.clipboardData) return;
            event.preventDefault();
            paste(event.clipboardData.getData('text/plain'), cell.closest('tr'), cell.dataset.columnKey);
        });
        root.WMS.ProductReceiptGrid.showPasteModal = function () {
            if (document.getElementById('pasteModal')) return;
            const modal = document.createElement('div');
            modal.id = 'pasteModal';
            modal.className = 'product-paste-modal';
            modal.innerHTML = '<div class="product-paste-dialog"><h5>Excel / WPS 粘贴导入</h5>' +
                '<p>默认五列：箱体编号、物料名称、规格、单位、数量。也可选择起始列后粘贴单列或单行。</p>' +
                '<label for="productPasteStart">起始列</label><select id="productPasteStart" class="form-select"></select>' +
                '<label for="pasteArea">粘贴内容</label><textarea id="pasteArea" class="form-control" rows="9"></textarea>' +
                '<p>相同名称和规格复用档案，每条入库明细保留。新物料在保存时从400001递增编号；单位须已建档。</p>' +
                '<div class="text-end"><button type="button" class="btn btn-secondary" data-paste-cancel>取消</button> ' +
                '<button type="button" class="btn btn-primary" data-paste-apply>确认导入</button></div></div>';
            const startSelect = modal.querySelector('select');
            fields.forEach(field => startSelect.add(new Option(field[2], field[0])));
            startSelect.value = 'box_no';
            const area = modal.querySelector('textarea');
            area.placeholder = ['PA03-1F-LP02', '配电柜', '800*675*2345', '台', '1'].join('\t');
            modal.querySelector('[data-paste-cancel]').addEventListener('click', () => modal.remove());
            modal.querySelector('[data-paste-apply]').addEventListener('click', () => {
                const selectedRow = anchor?.closest('tr');
                const row = selectedRow && body.contains(selectedRow) ? selectedRow :
                    (Array.from(body.rows).find(candidate => !used(candidate)) || options.addRow());
                const keys = fields.map(field => field[0]);
                if (paste(area.value, row, startSelect.value, keys)) modal.remove();
            });
            document.body.appendChild(modal);
            area.focus();
        };
    }
    const api = {parseTsv, planPaste, toTsv, init};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    root.WMS = root.WMS || {};
    root.WMS.ProductReceiptGrid = api;
})(typeof window !== 'undefined' ? window : globalThis);
