(function() {
    const PREFIX = window.__PRINT_EDITOR_CONFIG__.prefix;
    const TEMPLATE_ID = window.__PRINT_EDITOR_CONFIG__.templateId;
    const BASE_URL = '/' + PREFIX + '_print_template/' + TEMPLATE_ID + '/grid';
    const PREVIEW_URL = '/' + PREFIX + '_print_template/' + TEMPLATE_ID + '/preview_data';

    // 常用占位符（供速插）。label 是中文含义（chip 显示用），
    // value 是实际插入单元格的模板变量（改 value 会导致模板引擎取不到数据）
    const PLACEHOLDERS = [
        { label: '单号', value: '{order.order_no}' },
        { label: '日期', value: '{order.date}' },
        { label: '供应商', value: '{order.supplier.name}' },
        { label: '客户', value: '{order.customer}' },
        { label: '用途', value: '{order.purpose}' },
        { label: '备注', value: '{order.remark}' },
        { label: '领料人', value: '{order.picker}' },
        { label: '操作人', value: '{order.operator.username}' },
        { label: '合计数量', value: '{total_quantity}' },
        { label: '合计金额', value: '{total_amount}' },
        { label: '打印日期', value: '{print_date}' },
        { label: '物料编码', value: '{item.material.code}' },
        { label: '物料名称', value: '{item.material.name}' },
        { label: '规格', value: '{item.material.spec}' },
        { label: '品牌', value: '{item.material.brand}' },
        { label: '单位', value: '{item.material.unit.name}' },
        { label: '数量', value: '{item.quantity}' },
        { label: '单价', value: '{item.price}' },
        { label: '金额', value: '{item.amount}' },
        { label: '合同号', value: '{item.contract_no}' },
        { label: '项目名', value: '{item.project_name}' },
        { label: '明细备注', value: '{item.remark}' },
    ];

    /* ================================================================
     * 数据模型驱动引擎（PRINT-TEMPLATE-F06 v2）
     * cell = { t:文本, s:样式(后端键), rs, cs, cov:[r,c]|null }
     * 每个工作表：{ name, S, orig, undo, redo }
     * S = { cols:[{wu:Excel列宽单位}], rows:[{hu:行高磅值, cells:[cell]}] }
     * ================================================================ */
    let sheets = [];
    let activeIdx = 0;
    let S = null;                 // 当前工作表 state（引用 sheets[activeIdx].S）
    let undoStack = [], redoStack = [];
    let selA = null, selF = null; // 选区锚点/焦点 {r,c}（0 基）
    let selecting = false, editCtx = null, editSnapshot = null;
    let clip = null;              // 内部剪贴板
    let previewCtx = null;
    const pageCfg = { size: 'A4', orient: 'portrait', w: 210, h: 297, mt: 12, mb: 12, ml: 12, mr: 12, scale: 100 };
    const PAPER = { A4: [210, 297], A5: [148, 210], B5: [176, 250] };

    const gridTable = document.getElementById('gridTable');
    const keyTrap = document.getElementById('keyTrap');

    const R = () => S.rows.length, C = () => S.cols.length;
    function eachCell(fn) { for (let r = 0; r < R(); r++) for (let c = 0; c < C(); c++) fn(S.rows[r].cells[c], r, c); }
    function newCell() { return { t: '', s: {}, rs: 1, cs: 1, cov: null }; }
    function colLetter(n) { let s = ''; n++; while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; }
    function wuToPx(w) { return Math.round(w * 7 + 5); }   // Excel 列宽单位 → px（与预览一致）
    function huToPx(h) { return Math.round(h * 4 / 3); }   // 行高磅值 → px
    function escapeHtml(s) { const d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }
    function stableStringify(obj) {
        if (obj === null || typeof obj !== 'object') return JSON.stringify(obj);
        const keys = Object.keys(obj).sort();
        return '{' + keys.map(k => JSON.stringify(k) + ':' + stableStringify(obj[k])).join(',') + '}';
    }
    function styleOf(cell) { return (cell && cell.s) || {}; }

    function toast(msg, type) {
        type = type || 'success';
        const slot = document.getElementById('toastSlot');
        const el = document.createElement('div');
        el.className = 'alert alert-' + (type === 'error' ? 'danger' : type) + ' py-2 px-3 mb-2 shadow-sm';
        el.innerHTML = msg;
        slot.appendChild(el);
        setTimeout(() => el.remove(), 3500);
    }

    /* ==================== 网格 JSON → state ==================== */
    function gridToState(sheet) {
        const merges = sheet.merges || [];
        let R0 = sheet.max_row || 1, C0 = sheet.max_col || 1;
        merges.forEach(m => { R0 = Math.max(R0, m.row + m.rowspan - 1); C0 = Math.max(C0, m.col + m.colspan - 1); });
        (sheet.cells || []).forEach(cl => { R0 = Math.max(R0, cl.row); C0 = Math.max(C0, cl.col); });
        R0 = Math.max(R0, 8); C0 = Math.max(C0, 6);
        const st = { cols: [], rows: [] };
        for (let c = 1; c <= C0; c++) st.cols.push({ wu: (sheet.col_widths || {})[String(c)] || 8.43 });
        for (let r = 1; r <= R0; r++) {
            const row = { hu: (sheet.row_heights || {})[String(r)] || 0, cells: [] };
            for (let c = 1; c <= C0; c++) row.cells.push(newCell());
            st.rows.push(row);
        }
        (sheet.cells || []).forEach(cl => {
            const cell = st.rows[cl.row - 1].cells[cl.col - 1];
            cell.t = cl.value == null ? '' : String(cl.value);
            if (cl.style) cell.s = cl.style;
        });
        merges.forEach(m => {
            const anchor = st.rows[m.row - 1].cells[m.col - 1];
            anchor.rs = m.rowspan; anchor.cs = m.colspan;
            for (let i = 0; i < m.rowspan; i++) for (let j = 0; j < m.colspan; j++) {
                if (i === 0 && j === 0) continue;
                st.rows[m.row - 1 + i].cells[m.col - 1 + j].cov = [m.row - 1, m.col - 1];
            }
        });
        return st;
    }

    /* ==================== 渲染 ==================== */
    function styleToCssText(style) {
        style = style || {};
        let css = '';
        if (style.bold) css += 'font-weight:700;';
        if (style.italic) css += 'font-style:italic;';
        if (style.underline) css += 'text-decoration:underline;';
        if (style.font_name) css += "font-family:'" + style.font_name + "';";
        if (style.font_size) css += 'font-size:' + style.font_size + 'pt;';
        if (style.font_color) css += 'color:' + style.font_color + ';';
        if (style.bg_color) css += 'background:' + style.bg_color + ';';
        if (style.h_align) css += 'text-align:' + style.h_align + ';';
        css += 'vertical-align:' + (style.v_align === 'center' ? 'middle' : (style.v_align || 'middle')) + ';';
        if (style.wrap) css += 'white-space:pre-wrap;';
        const b = style.border || {};
        ['top', 'right', 'bottom', 'left'].forEach(function(e) {
            const v = borderEdgeCss(b[e]);
            if (v) css += 'border-' + e + ':' + v + ';';
        });
        return css;
    }
    function borderEdgeCss(v) {
        if (!v) return '';
        const w = { hair: '1px', thin: '1px', medium: '2px', thick: '3px', dashed: '1px', dotted: '1px', double: '3px' }[v] || '1px';
        return w + ' ' + (v === 'dashed' ? 'dashed' : v === 'dotted' ? 'dotted' : v === 'double' ? 'double' : 'solid') + ' #334155';
    }

    function render() {
        let html = '<colgroup><col style="width:42px">';
        S.cols.forEach(c => { html += '<col style="width:' + wuToPx(c.wu) + 'px">'; });
        html += '</colgroup><thead><tr><th class="corner" title="全选"></th>';
        S.cols.forEach((_, c) => { html += '<th class="colh" data-c="' + c + '" title="选中整列">' + colLetter(c) + '</th>'; });
        html += '</tr></thead><tbody>';
        S.rows.forEach((row, r) => {
            html += '<tr' + (row.hu ? ' style="height:' + huToPx(row.hu) + 'px"' : '') + '>';
            html += '<th class="rowh" data-r="' + r + '" title="选中整行">' + (r + 1) + '</th>';
            row.cells.forEach((cell, c) => {
                if (cell.cov) return;
                const span = (cell.rs > 1 ? ' rowspan="' + cell.rs + '"' : '') + (cell.cs > 1 ? ' colspan="' + cell.cs + '"' : '');
                const css = styleToCssText(cell.s);
                html += '<td class="cell" data-r="' + r + '" data-c="' + c + '"' + span +
                    (css ? ' style="' + css + '"' : '') + '>' + escapeHtml(cell.t) + '</td>';
            });
            html += '</tr>';
        });
        html += '</tbody>';
        gridTable.innerHTML = html;
        document.getElementById('sizeInfo').textContent = R() + ' × ' + C();
        renderSelection();
    }

    function normSel() {
        if (!selA || !selF) return null;
        return { r1: Math.min(selA.r, selF.r), r2: Math.max(selA.r, selF.r), c1: Math.min(selA.c, selF.c), c2: Math.max(selA.c, selF.c) };
    }
    function renderSelection() {
        gridTable.querySelectorAll('td.sel').forEach(td => td.classList.remove('sel'));
        const rect = normSel(); if (!rect) return;
        const ae = document.activeElement;
        if (!editCtx && ae !== keyTrap && !/^(INPUT|SELECT|TEXTAREA)$/.test(ae ? ae.tagName : '')) keyTrap.focus();
        gridTable.querySelectorAll('td.cell').forEach(td => {
            const r = +td.dataset.r, c = +td.dataset.c;
            const cell = S.rows[r].cells[c];
            if (r + cell.rs - 1 >= rect.r1 && r <= rect.r2 && c + cell.cs - 1 >= rect.c1 && c <= rect.c2)
                td.classList.add('sel');
        });
        syncToolbar();
    }
    function selectedCells() {
        const rect = normSel(); if (!rect) return [];
        const out = [];
        eachCell((cell, r, c) => {
            if (cell.cov) return;
            if (r + cell.rs - 1 >= rect.r1 && r <= rect.r2 && c + cell.cs - 1 >= rect.c1 && c <= rect.c2) out.push(cell);
        });
        return out;
    }

    /* ==================== 撤销/重做（按工作表） ==================== */
    function pushHistory() {
        undoStack.push(structuredClone(S));
        if (undoStack.length > 100) undoStack.shift();
        redoStack.length = 0;
        refreshDirty();
    }
    function afterRestore() {
        if (selA) {
            selA = { r: Math.min(selA.r, R() - 1), c: Math.min(selA.c, C() - 1) };
            selF = { r: Math.min(selF.r, R() - 1), c: Math.min(selF.c, C() - 1) };
        }
        render();
    }
    function undo() {
        if (editCtx) exitEdit();
        if (!undoStack.length) return;
        redoStack.push(structuredClone(S));
        sheets[activeIdx].S = S = undoStack.pop();
        afterRestore(); refreshDirty();
    }
    function redo() {
        if (editCtx) exitEdit();
        if (!redoStack.length) return;
        undoStack.push(structuredClone(S));
        sheets[activeIdx].S = S = redoStack.pop();
        afterRestore(); refreshDirty();
    }
    function sheetDirty(i) {
        return stableStringify(sheets[i].S) !== stableStringify(sheets[i].orig);
    }
    function anyDirty() { return sheets.some((_, i) => sheetDirty(i)); }
    function refreshDirty() {
        document.getElementById('btnSave').innerHTML = anyDirty()
            ? '<i class="bi bi-save"></i> ● 保存模板' : '<i class="bi bi-save"></i> 保存模板';
        document.querySelectorAll('#sheetTabs .sheet-tab').forEach((tab, i) => {
            const dot = tab.querySelector('.dirty-dot');
            if (sheetDirty(i)) { if (!dot) tab.insertAdjacentHTML('beforeend', ' <span class="dirty-dot">●</span>'); }
            else if (dot) dot.remove();
        });
    }
    window.addEventListener('beforeunload', e => {
        if (editCtx) exitEdit();
        if (anyDirty()) { e.preventDefault(); e.returnValue = ''; }
    });

    /* ==================== 结构操作（模型层） ==================== */
    function insertRow(at) {
        at = Math.max(0, Math.min(at, R()));
        const covered = new Array(C()).fill(null);
        eachCell((cell, r, c) => {
            if (cell.cov || cell.rs <= 1) return;
            if (r < at && r + cell.rs - 1 >= at) {
                cell.rs++;
                for (let j = c; j < c + cell.cs; j++) covered[j] = [r, c];
            }
        });
        const cells = [];
        for (let c = 0; c < C(); c++) { const nc = newCell(); if (covered[c]) nc.cov = covered[c]; cells.push(nc); }
        S.rows.splice(at, 0, { hu: 0, cells });
        eachCell(cell => { if (cell.cov && cell.cov[0] >= at) cell.cov = [cell.cov[0] + 1, cell.cov[1]]; });
    }
    function deleteRow(r) {
        if (R() <= 1) return toast('至少保留一行', 'warning');
        for (let c = 0; c < C(); c++) {
            const cell = S.rows[r].cells[c];
            if (cell.cov) {
                const a = S.rows[cell.cov[0]].cells[cell.cov[1]];
                a.rs--; c += a.cs - 1;
            } else if (cell.rs > 1) {
                const target = S.rows[r + 1].cells[c];
                target.t = cell.t; target.s = cell.s; target.rs = cell.rs - 1; target.cs = cell.cs; target.cov = null;
                for (let i = r + 1; i < r + cell.rs; i++)
                    for (let j = c; j < c + cell.cs; j++) {
                        if (i === r + 1 && j === c) continue;
                        S.rows[i].cells[j].cov = [r + 1, c];
                    }
                c += cell.cs - 1;
            } else c += (cell.cs || 1) - 1;
        }
        S.rows.splice(r, 1);
        eachCell(cell => { if (cell.cov && cell.cov[0] > r) cell.cov = [cell.cov[0] - 1, cell.cov[1]]; });
    }
    function insertCol(at) {
        at = Math.max(0, Math.min(at, C()));
        const covMark = {};
        eachCell((cell, r, c) => {
            if (cell.cov || cell.cs <= 1) return;
            if (c < at && c + cell.cs - 1 >= at) {
                cell.cs++;
                for (let i = r; i < r + cell.rs; i++) covMark[i] = [r, c];
            }
        });
        S.rows.forEach((row, r) => {
            const nc = newCell(); if (covMark[r]) nc.cov = covMark[r];
            row.cells.splice(at, 0, nc);
        });
        S.cols.splice(at, 0, { wu: 8.43 });
        eachCell(cell => { if (cell.cov && cell.cov[1] >= at) cell.cov = [cell.cov[0], cell.cov[1] + 1]; });
    }
    function deleteCol(c) {
        if (C() <= 1) return toast('至少保留一列', 'warning');
        for (let r = 0; r < R(); r++) {
            const cell = S.rows[r].cells[c];
            if (cell.cov) {
                const a = S.rows[cell.cov[0]].cells[cell.cov[1]];
                a.cs--; r += a.rs - 1;
            } else if (cell.cs > 1) {
                const target = S.rows[r].cells[c + 1];
                target.t = cell.t; target.s = cell.s; target.rs = cell.rs; target.cs = cell.cs - 1; target.cov = null;
                for (let j = c + 1; j < c + cell.cs; j++)
                    for (let i = r; i < r + cell.rs; i++) {
                        if (i === r && j === c + 1) continue;
                        S.rows[i].cells[j].cov = [r, c + 1];
                    }
                r += cell.rs - 1;
            } else r += (cell.rs || 1) - 1;
        }
        S.rows.forEach(row => row.cells.splice(c, 1));
        S.cols.splice(c, 1);
        eachCell(cell => { if (cell.cov && cell.cov[1] > c) cell.cov = [cell.cov[0], cell.cov[1] - 1]; });
    }
    function canMerge(rect) {
        for (let r = rect.r1; r <= rect.r2; r++) for (let c = rect.c1; c <= rect.c2; c++) {
            const cell = S.rows[r].cells[c];
            const ar = cell.cov ? cell.cov[0] : r, ac = cell.cov ? cell.cov[1] : c;
            const a = S.rows[ar].cells[ac];
            if (ar < rect.r1 || ac < rect.c1 || ar + a.rs - 1 > rect.r2 || ac + a.cs - 1 > rect.c2) return false;
        }
        return true;
    }
    function mergeSel() {
        const rect = normSel(); if (!rect) return;
        if (rect.r1 === rect.r2 && rect.c1 === rect.c2) return;
        if (!canMerge(rect)) return toast('选区切割了已有合并单元格，请先取消合并', 'warning');
        const anchor = S.rows[rect.r1].cells[rect.c1];
        const texts = [];
        for (let r = rect.r1; r <= rect.r2; r++) for (let c = rect.c1; c <= rect.c2; c++) {
            if (r === rect.r1 && c === rect.c1) continue;
            const old = S.rows[r].cells[c];
            if (!old.cov && old.t.trim()) texts.push(old.t.trim());
            const nc = newCell(); nc.cov = [rect.r1, rect.c1]; nc.s = old.s || {};
            S.rows[r].cells[c] = nc;
        }
        if (texts.length) anchor.t = (anchor.t.trim() + ' ' + texts.join(' ')).trim();
        anchor.rs = rect.r2 - rect.r1 + 1;
        anchor.cs = rect.c2 - rect.c1 + 1;
    }
    function unmergeSel() {
        const rect = normSel(); if (!rect) return;
        eachCell((cell, r, c) => {
            if (cell.cov || (cell.rs === 1 && cell.cs === 1)) return;
            const hit = !(r + cell.rs - 1 < rect.r1 || r > rect.r2 || c + cell.cs - 1 < rect.c1 || c > rect.c2);
            if (!hit) return;
            for (let i = r; i < r + cell.rs; i++) for (let j = c; j < c + cell.cs; j++) {
                if (i === r && j === c) continue;
                S.rows[i].cells[j].cov = null;
            }
            cell.rs = 1; cell.cs = 1;
        });
    }

    function opRowCol(op) {
        exitEdit();
        const rect = normSel();
        if (!rect && op !== 'insRowD') return toast('请先选中单元格/行/列', 'warning');
        if (rect && op === 'delRow' && !confirm('确定删除第 ' + (rect.r1 + 1) + ' ~ ' + (rect.r2 + 1) + ' 行吗？')) return;
        if (rect && op === 'delCol' && !confirm('确定删除第 ' + colLetter(rect.c1) + ' ~ ' + colLetter(rect.c2) + ' 列吗？')) return;
        pushHistory();
        switch (op) {
            case 'insRowU': insertRow(rect.r1); selF = { r: selF.r + 1, c: selF.c }; break;
            case 'insRowD': insertRow(rect ? rect.r2 + 1 : R()); break;
            case 'delRow':
                for (let r = rect.r2; r >= rect.r1; r--) { if (R() <= 1) break; deleteRow(r); }
                selA = selF = null; break;
            case 'insColL': insertCol(rect.c1); selF = { r: selF.r, c: selF.c + 1 }; break;
            case 'insColR': insertCol(rect.c2 + 1); break;
            case 'delCol':
                for (let c = rect.c2; c >= rect.c1; c--) { if (C() <= 1) break; deleteCol(c); }
                selA = selF = null; break;
            case 'merge': mergeSel(); break;
            case 'unmerge': unmergeSel(); break;
        }
        render();
    }

    /* ==================== 编辑 ==================== */
    function enterEdit(td, clear) {
        exitEdit();
        if (!editSnapshot) editSnapshot = structuredClone(S);
        const r = +td.dataset.r, c = +td.dataset.c;
        const cell = S.rows[r].cells[c];
        editCtx = { r, c, td };
        if (clear) { cell.t = ''; td.textContent = ''; }
        td.contentEditable = 'true';
        td.focus();
        const range = document.createRange(); range.selectNodeContents(td); range.collapse(false);
        const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
        td.addEventListener('blur', () => { if (editCtx && editCtx.td === td) exitEdit(); }, { once: true });
    }
    function exitEdit() {
        if (!editCtx) return;
        const { r, c, td } = editCtx;
        td.contentEditable = 'false';
        S.rows[r].cells[c].t = td.innerText.replace(/\n+$/, '');
        if (editSnapshot && editSnapshot.rows[r].cells[c].t !== S.rows[r].cells[c].t) {
            undoStack.push(editSnapshot);
            if (undoStack.length > 100) undoStack.shift();
            redoStack.length = 0;
            refreshDirty();
        }
        editSnapshot = null;
        editCtx = null;
    }
    function cancelEdit() {
        if (!editCtx) return;
        const { r, c, td } = editCtx;
        if (editSnapshot) { S.rows[r].cells[c].t = editSnapshot.rows[r].cells[c].t; td.textContent = S.rows[r].cells[c].t; }
        editSnapshot = null;
        td.contentEditable = 'false';
        editCtx = null;
    }
    function flushKeyTrap() {
        if (editCtx) { keyTrap.value = ''; return; }
        const v = keyTrap.value;
        keyTrap.value = '';
        if (!v || !selA) return;
        const td = gridTable.querySelector('td[data-r="' + selA.r + '"][data-c="' + selA.c + '"]');
        if (!td) return;
        editSnapshot = structuredClone(S);
        S.rows[selA.r].cells[selA.c].t = v;   // Excel 行为：直接打字替换原内容
        td.textContent = v;
        enterEdit(td, false);
    }
    keyTrap.addEventListener('input', e => { if (!e.isComposing) flushKeyTrap(); });
    keyTrap.addEventListener('compositionend', flushKeyTrap);

    /* ==================== 鼠标/键盘/右键 ==================== */
    gridTable.addEventListener('mousedown', e => {
        const th = e.target.closest('th');
        if (th && e.button !== 2) {
            exitEdit();
            if (th.classList.contains('corner')) { selA = { r: 0, c: 0 }; selF = { r: R() - 1, c: C() - 1 }; }
            else if (th.classList.contains('colh')) { const c = +th.dataset.c; selA = { r: 0, c }; selF = { r: R() - 1, c }; }
            else if (th.classList.contains('rowh')) { const r = +th.dataset.r; selA = { r, c: 0 }; selF = { r, c: C() - 1 }; }
            renderSelection();
            e.preventDefault();
            return;
        }
        const td = e.target.closest('td');
        if (!td || e.button === 2) return;
        if (editCtx && editCtx.td === td) return;
        exitEdit();
        const r = +td.dataset.r, c = +td.dataset.c;
        if (e.shiftKey && selA) selF = { r, c };
        else { selA = { r, c }; selF = { r, c }; selecting = true; }
        renderSelection();
        e.preventDefault();
    });
    gridTable.addEventListener('mouseover', e => {
        if (!selecting) return;
        const td = e.target.closest('td'); if (!td) return;
        selF = { r: +td.dataset.r, c: +td.dataset.c };
        renderSelection();
    });
    document.addEventListener('mouseup', () => selecting = false);
    gridTable.addEventListener('dblclick', e => {
        const td = e.target.closest('td'); if (td) enterEdit(td, false);
    });

    document.addEventListener('keydown', e => {
        if (editCtx) {
            if (e.key === 'Escape') { cancelEdit(); render(); }
            return;
        }
        if ((e.ctrlKey || e.metaKey) && !e.altKey) {
            const k = e.key.toLowerCase();
            if (k === 'z' && !e.shiftKey) { e.preventDefault(); undo(); return; }
            if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); redo(); return; }
        }
        const rect = normSel(); if (!rect) return;
        if (e.key === 'Escape') { clip = null; return; }
        if (e.key === 'Delete' || e.key === 'Backspace') {
            const cells = selectedCells();
            if (cells.some(cell => cell.t)) pushHistory();
            cells.forEach(cell => cell.t = '');
            render(); e.preventDefault();
        } else if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
            const d = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[e.key];
            const nr = Math.max(0, Math.min(R() - 1, selA.r + d[0]));
            const nc = Math.max(0, Math.min(C() - 1, selA.c + d[1]));
            selA = selF = { r: nr, c: nc };
            renderSelection(); e.preventDefault();
        } else if (e.key === 'Enter') {
            const td = gridTable.querySelector('td[data-r="' + selA.r + '"][data-c="' + selA.c + '"]');
            if (td) enterEdit(td, false);
            e.preventDefault();
        }
    });

    const ctxmenu = document.getElementById('ctxmenu');
    gridTable.addEventListener('contextmenu', e => {
        const td = e.target.closest('td');
        if (td) {
            const r = +td.dataset.r, c = +td.dataset.c;
            const rect = normSel();
            if (!(rect && r >= rect.r1 && r <= rect.r2 && c >= rect.c1 && c <= rect.c2)) {
                selA = selF = { r, c };
                renderSelection();
            }
        }
        e.preventDefault();
        ctxmenu.style.display = 'block';
        ctxmenu.style.left = Math.min(e.clientX, innerWidth - 170) + 'px';
        ctxmenu.style.top = Math.min(e.clientY, innerHeight - 260) + 'px';
    });
    document.addEventListener('click', e => { if (!ctxmenu.contains(e.target)) ctxmenu.style.display = 'none'; });
    ctxmenu.querySelectorAll('.mi').forEach(mi => mi.addEventListener('click', () => {
        ctxmenu.style.display = 'none';
        opRowCol(mi.dataset.op);
    }));

    /* ==================== 复制/剪切/粘贴 ==================== */
    function buildTSV(rect) {
        const lines = [];
        for (let r = rect.r1; r <= rect.r2; r++) {
            const row = [];
            for (let c = rect.c1; c <= rect.c2; c++) {
                const cell = S.rows[r].cells[c];
                row.push(cell.cov ? '' : cell.t.replace(/\n/g, ' '));
            }
            lines.push(row.join('\t'));
        }
        return lines.join('\n');
    }
    function setInternalClip(rect, cut) {
        clip = { cut, rect: { ...rect }, cells: [] };
        for (let r = rect.r1; r <= rect.r2; r++) {
            const row = [];
            for (let c = rect.c1; c <= rect.c2; c++) {
                const cell = structuredClone(S.rows[r].cells[c]);
                if (cell.cov) cell.cov = [cell.cov[0] - rect.r1, cell.cov[1] - rect.c1];
                row.push(cell);
            }
            clip.cells.push(row);
        }
    }
    function unmergeRegion(rect) {
        eachCell((cell, r, c) => {
            if (cell.cov || (cell.rs === 1 && cell.cs === 1)) return;
            const hit = !(r + cell.rs - 1 < rect.r1 || r > rect.r2 || c + cell.cs - 1 < rect.c1 || c > rect.c2);
            if (!hit) return;
            for (let i = r; i < r + cell.rs; i++) for (let j = c; j < c + cell.cs; j++) {
                if (i === r && j === c) continue;
                S.rows[i].cells[j].cov = null;
            }
            cell.rs = 1; cell.cs = 1;
        });
    }
    function clearRegion(rect) {
        unmergeRegion(rect);
        for (let r = rect.r1; r <= rect.r2; r++)
            for (let c = rect.c1; c <= rect.c2; c++)
                S.rows[r].cells[c] = newCell();
    }
    function pasteInternal() {
        const rect = normSel(); if (!rect || !clip) return;
        const r0 = rect.r1, c0 = rect.c1;
        const pr = clip.cells.length, pc = clip.cells[0].length;
        pushHistory();
        while (R() < r0 + pr) insertRow(R());
        while (C() < c0 + pc) insertCol(C());
        unmergeRegion({ r1: r0, c1: c0, r2: r0 + pr - 1, c2: c0 + pc - 1 });
        for (let i = 0; i < pr; i++) for (let j = 0; j < pc; j++) {
            const nc = structuredClone(clip.cells[i][j]);
            if (nc.cov) nc.cov = [r0 + nc.cov[0], c0 + nc.cov[1]];
            S.rows[r0 + i].cells[c0 + j] = nc;
        }
        if (clip.cut) { clearRegion(clip.rect); clip = null; }
        selA = { r: r0, c: c0 }; selF = { r: r0 + pr - 1, c: c0 + pc - 1 };
        render();
    }
    function pasteTSV(text) {
        const rect = normSel(); if (!rect) return;
        const rows = text.replace(/\r\n/g, '\n').replace(/\n$/, '').split('\n').map(l => l.split('\t'));
        const r0 = rect.r1, c0 = rect.c1;
        pushHistory();
        while (R() < r0 + rows.length) insertRow(R());
        const maxC = Math.max(...rows.map(r => r.length));
        while (C() < c0 + maxC) insertCol(C());
        unmergeRegion({ r1: r0, c1: c0, r2: r0 + rows.length - 1, c2: c0 + maxC - 1 });
        rows.forEach((row, i) => row.forEach((v, j) => { S.rows[r0 + i].cells[c0 + j].t = v; }));
        selA = { r: r0, c: c0 }; selF = { r: r0 + rows.length - 1, c: c0 + maxC - 1 };
        render();
    }
    document.addEventListener('copy', e => {
        if (editCtx) return;
        const rect = normSel(); if (!rect || !e.clipboardData) return;
        e.clipboardData.setData('text/plain', buildTSV(rect));
        setInternalClip(rect, false);
        e.preventDefault();
    });
    document.addEventListener('cut', e => {
        if (editCtx) return;
        const rect = normSel(); if (!rect || !e.clipboardData) return;
        e.clipboardData.setData('text/plain', buildTSV(rect));
        setInternalClip(rect, true);
        e.preventDefault();
    });
    document.addEventListener('paste', e => {
        if (editCtx) return;
        const rect = normSel(); if (!rect) return;
        if (clip) { pasteInternal(); e.preventDefault(); return; }
        const text = e.clipboardData ? e.clipboardData.getData('text/plain') : '';
        if (text) { pasteTSV(text); e.preventDefault(); }
    });

    /* ==================== 工具栏：样式 ==================== */
    function setStyleKey(k, v) {
        const cells = selectedCells(); if (!cells.length) return;
        pushHistory();
        cells.forEach(cell => { if (v == null) delete cell.s[k]; else cell.s[k] = v; });
        render();
    }
    function toggleStyleKey(k) {
        const cells = selectedCells(); if (!cells.length) return;
        pushHistory();
        const nv = !cells[0].s[k];
        cells.forEach(cell => { if (nv) cell.s[k] = true; else delete cell.s[k]; });
        render();
    }
    document.getElementById('btnUndo').onclick = undo;
    document.getElementById('btnRedo').onclick = redo;
    ['insRowU', 'insRowD', 'delRow', 'insColL', 'insColR', 'delCol', 'merge', 'unmerge'].forEach(op => {
        const id = { insRowU: 'btnInsRowU', insRowD: 'btnInsRowD', delRow: 'btnDelRow', insColL: 'btnInsColL', insColR: 'btnInsColR', delCol: 'btnDelCol', merge: 'btnMerge', unmerge: 'btnUnmerge' }[op];
        document.getElementById(id).onclick = () => opRowCol(op);
    });
    document.getElementById('tbFontName').onchange = e => setStyleKey('font_name', e.target.value || null);
    document.getElementById('tbFontSize').onchange = e => setStyleKey('font_size', e.target.value ? +e.target.value : null);
    document.getElementById('tbFontColor').oninput = e => setStyleKey('font_color', e.target.value);
    document.getElementById('tbBgColor').oninput = e => setStyleKey('bg_color', e.target.value);
    document.getElementById('tbFontColorClear').onclick = () => setStyleKey('font_color', null);
    document.getElementById('tbBgColorClear').onclick = () => setStyleKey('bg_color', null);
    document.getElementById('tbBold').onclick = () => toggleStyleKey('bold');
    document.getElementById('tbItalic').onclick = () => toggleStyleKey('italic');
    document.getElementById('tbUnderline').onclick = () => toggleStyleKey('underline');
    document.getElementById('tbWrap').onclick = () => toggleStyleKey('wrap');
    [['tbHLeft', 'h_align', 'left'], ['tbHCenter', 'h_align', 'center'], ['tbHRight', 'h_align', 'right'],
     ['tbVTop', 'v_align', 'top'], ['tbVCenter', 'v_align', 'center'], ['tbVBottom', 'v_align', 'bottom']].forEach(([id, k, v]) => {
        document.getElementById(id).onclick = () => setStyleKey(k, v);
    });
    document.querySelectorAll('[data-border]').forEach(a => a.addEventListener('click', () => {
        const mode = a.dataset.border;
        const rect = normSel(); if (!rect) return toast('请先选中单元格', 'warning');
        pushHistory();
        eachCell((cell, r, c) => {
            if (r < rect.r1 || r > rect.r2 || c < rect.c1 || c > rect.c2) return;
            if (mode === 'all') cell.s.border = { top: 'thin', right: 'thin', bottom: 'thin', left: 'thin' };
            else if (mode === 'none') delete cell.s.border;
            else if (mode === 'outline') {
                cell.s.border = cell.s.border || {};
                if (r === rect.r1) cell.s.border.top = 'thin';
                if (r === rect.r2) cell.s.border.bottom = 'thin';
                if (c === rect.c1) cell.s.border.left = 'thin';
                if (c === rect.c2) cell.s.border.right = 'thin';
            }
        });
        render();
    }));
    document.getElementById('btnColW').onclick = () => {
        const rect = normSel(); if (!rect) return toast('请先选中单元格/列', 'warning');
        const w = +document.getElementById('tbColWidth').value;
        if (!w || w <= 0) return toast('请输入有效列宽（Excel 宽度单位，如 8.43）', 'warning');
        pushHistory();
        for (let c = rect.c1; c <= rect.c2; c++) S.cols[c].wu = w;
        render();
    };
    document.getElementById('btnRowH').onclick = () => {
        const rect = normSel(); if (!rect) return toast('请先选中单元格/行', 'warning');
        const h = +document.getElementById('tbRowHeight').value;
        if (!h || h <= 0) return toast('请输入有效行高（磅）', 'warning');
        pushHistory();
        for (let r = rect.r1; r <= rect.r2; r++) S.rows[r].hu = h;
        render();
    };
    function syncToolbar() {
        const cells = selectedCells(); if (!cells.length) return;
        const s = cells[0].s || {};
        document.getElementById('tbBold').classList.toggle('active', !!s.bold);
        document.getElementById('tbItalic').classList.toggle('active', !!s.italic);
        document.getElementById('tbUnderline').classList.toggle('active', !!s.underline);
        document.getElementById('tbWrap').classList.toggle('active', !!s.wrap);
        ['left', 'center', 'right'].forEach(v => document.getElementById('tbH' + v[0].toUpperCase() + v.slice(1)).classList.toggle('active', s.h_align === v));
        [['tbVTop', 'top'], ['tbVCenter', 'center'], ['tbVBottom', 'bottom']].forEach(([id, v]) => document.getElementById(id).classList.toggle('active', s.v_align === v));
        if (s.font_size) document.getElementById('tbFontSize').value = s.font_size;
        if (s.font_name) document.getElementById('tbFontName').value = s.font_name;
    }

    /* ==================== 占位符 ==================== */
    function buildPlaceholders() {
        const wrap = document.getElementById('phChips');
        wrap.innerHTML = '';
        PLACEHOLDERS.forEach(function(p) {
            const chip = document.createElement('span');
            chip.className = 'ph-chip';
            chip.textContent = p.label;
            chip.title = p.value + '：点击插入到当前编辑的单元格';
            chip.onmousedown = function(e) { e.preventDefault(); };
            chip.onclick = function() { insertPlaceholder(p.value); };
            wrap.appendChild(chip);
        });
    }
    function insertPlaceholder(p) {
        if (editCtx) {
            editCtx.td.focus();
            document.execCommand('insertText', false, p);
        } else {
            const rect = normSel(); if (!rect) return toast('请先选中一个单元格', 'warning');
            pushHistory();
            const cell = S.rows[selA.r].cells[selA.c];
            cell.t = cell.t ? cell.t + ' ' + p : p;
            render();
        }
    }

    /* ==================== 工作表标签 ==================== */
    function buildTabs() {
        const tabs = document.getElementById('sheetTabs');
        tabs.innerHTML = '';
        sheets.forEach((sh, i) => {
            const tab = document.createElement('span');
            tab.className = 'sheet-tab' + (i === activeIdx ? ' active' : '');
            tab.textContent = sh.name;
            tab.onclick = () => switchSheet(i);
            tabs.appendChild(tab);
        });
    }
    function switchSheet(i) {
        if (i === activeIdx) return;
        exitEdit();
        sheets[activeIdx].undo = undoStack; sheets[activeIdx].redo = redoStack;
        activeIdx = i;
        S = sheets[i].S;
        undoStack = sheets[i].undo; redoStack = sheets[i].redo;
        selA = selF = null; clip = null;
        buildTabs(); render(); refreshDirty();
    }

    /* ==================== 加载 ==================== */
    function loadGrid() {
        WMS.api.get(BASE_URL).then(function(res) {
            sheets = (res.sheets || []).map(function(sh) {
                const st = gridToState(sh);
                return { name: sh.name, S: st, orig: structuredClone(st), undo: [], redo: [] };
            });
            if (!sheets.length) {
                const st = { cols: Array.from({ length: 9 }, () => ({ wu: 8.43 })), rows: Array.from({ length: 8 }, () => ({ hu: 0, cells: Array.from({ length: 9 }, newCell) })) };
                sheets = [{ name: 'Sheet1', S: st, orig: structuredClone(st), undo: [], redo: [] }];
            }
            activeIdx = 0;
            S = sheets[0].S;
            undoStack = sheets[0].undo; redoStack = sheets[0].redo;
            buildTabs(); render(); refreshDirty();
            document.getElementById('statusInfo').textContent = '已加载 ' + sheets.length + ' 个工作表';
        }).catch(function(err) {
            document.getElementById('statusInfo').textContent = '加载失败';
            toast(escapeHtml(err.message || '模板网格加载失败'), 'error');
        });
    }

    /* ==================== 保存（全状态 DIFF，坐标一致无平移） ==================== */
    function cellText(st, r, c) { // 1 基坐标；越界/被覆盖 → ''
        if (r > st.rows.length || c > st.cols.length) return '';
        const cell = st.rows[r - 1].cells[c - 1];
        return cell.cov ? '' : cell.t;
    }
    function cellStyleAt(st, r, c) {
        if (r > st.rows.length || c > st.cols.length) return {};
        return styleOf(st.rows[r - 1].cells[c - 1]);
    }
    function stylePatch(oldS, newS) {
        const patch = {};
        const keys = new Set([...Object.keys(oldS || {}), ...Object.keys(newS || {})]);
        keys.forEach(k => {
            if (k === 'border') {
                const bp = {};
                const edges = new Set([...Object.keys((oldS || {}).border || {}), ...Object.keys((newS || {}).border || {})]);
                edges.forEach(e => {
                    const ov = ((oldS || {}).border || {})[e] || null;
                    const nv = ((newS || {}).border || {})[e] || null;
                    if (ov !== nv) bp[e] = nv;
                });
                if (Object.keys(bp).length) patch.border = bp;
            } else {
                const ov = (oldS || {})[k] !== undefined ? (oldS || {})[k] : null;
                const nv = (newS || {})[k] !== undefined ? (newS || {})[k] : null;
                if (ov !== nv) patch[k] = nv;
            }
        });
        return patch;
    }
    function mergeList(st) {
        const out = [];
        for (let r = 0; r < st.rows.length; r++) for (let c = 0; c < st.cols.length; c++) {
            const cell = st.rows[r].cells[c];
            if (!cell.cov && (cell.rs > 1 || cell.cs > 1))
                out.push({ row: r + 1, col: c + 1, rowspan: cell.rs, colspan: cell.cs });
        }
        return out;
    }
    function buildSheetPayload(sh) {
        const N = sh.S, O = sh.orig;
        const FR = N.rows.length, FC = N.cols.length;
        const OR = O.rows.length, OC = O.cols.length;
        const MR = Math.max(FR, OR), MC = Math.max(FC, OC);
        const upserts = [], styles = [];
        for (let r = 1; r <= MR; r++) for (let c = 1; c <= MC; c++) {
            const fv = cellText(N, r, c), ov = cellText(O, r, c);
            if (fv !== ov) upserts.push([r, c, fv]);
            const os = cellStyleAt(O, r, c), ns = cellStyleAt(N, r, c);
            if (stableStringify(os) !== stableStringify(ns)) styles.push([r, c, stylePatch(os, ns)]);
        }
        const col_widths = {};
        for (let c = 1; c <= FC; c++) {
            const wu = N.cols[c - 1].wu;
            const ow = c <= OC ? O.cols[c - 1].wu : null;
            if (wu && wu !== ow) col_widths[String(c)] = wu;
        }
        const row_heights = {};
        for (let r = 1; r <= FR; r++) {
            const hu = N.rows[r - 1].hu;
            const oh = r <= OR ? O.rows[r - 1].hu : 0;
            if (hu && hu !== oh) row_heights[String(r)] = hu;
        }
        const oMerges = mergeList(O), nMerges = mergeList(N);
        const key = m => m.row + ':' + m.col + ':' + m.rowspan + ':' + m.colspan;
        const nKeys = new Set(nMerges.map(key)), oKeys = new Set(oMerges.map(key));
        const unmerges = oMerges.filter(m => !nKeys.has(key(m))).map(m => [m.row, m.col]);
        const merges = nMerges.filter(m => !oKeys.has(key(m)));
        const payload = { name: sh.name, upserts, del_rows: [], styles, col_widths, row_heights, merges, unmerges };
        const count = upserts.length + styles.length + merges.length + unmerges.length +
            Object.keys(col_widths).length + Object.keys(row_heights).length;
        return count ? payload : null;
    }
    function onSave() {
        exitEdit();
        const payload = sheets.map(buildSheetPayload).filter(Boolean);
        if (!payload.length) return toast('没有需要保存的改动', 'warning');
        WMS.api.post(BASE_URL, { sheets: payload }).then(function(res) {
            sheets.forEach(sh => { sh.orig = structuredClone(sh.S); });
            refreshDirty();
            document.getElementById('statusInfo').textContent = '已保存 ' + new Date().toLocaleTimeString();
            toast(escapeHtml(res.msg || '模板已更新'));
        }).catch(function(err) {
            toast(escapeHtml(err.message || '保存失败'), 'error');
        });
    }
    document.getElementById('btnSave').onclick = onSave;

    /* ==================== 页面设置 ==================== */
    function pageDims() { return pageCfg.orient === 'portrait' ? [pageCfg.w, pageCfg.h] : [pageCfg.h, pageCfg.w]; }
    function applyPageStyle() {
        const [w, h] = pageDims();
        document.getElementById('pageStyle').textContent =
            '@page{size:' + w + 'mm ' + h + 'mm;margin:' + pageCfg.mt + 'mm ' + pageCfg.mr + 'mm ' + pageCfg.mb + 'mm ' + pageCfg.ml + 'mm;}';
    }
    const pageModal = () => bootstrap.Modal.getOrCreateInstance(document.getElementById('pageModal'));
    document.getElementById('btnPageSetup').onclick = () => {
        document.getElementById('pgSize').value = pageCfg.size;
        document.getElementById('pgOrient').value = pageCfg.orient;
        document.getElementById('pgW').value = pageCfg.w; document.getElementById('pgH').value = pageCfg.h;
        document.getElementById('pgMt').value = pageCfg.mt; document.getElementById('pgMb').value = pageCfg.mb;
        document.getElementById('pgMl').value = pageCfg.ml; document.getElementById('pgMr').value = pageCfg.mr;
        document.getElementById('pgScale').value = pageCfg.scale;
        document.getElementById('customSize').style.display = pageCfg.size === 'custom' ? 'flex' : 'none';
        pageModal().show();
    };
    document.getElementById('pgSize').onchange = e => {
        document.getElementById('customSize').style.display = e.target.value === 'custom' ? 'flex' : 'none';
    };
    document.getElementById('btnPageOk').onclick = () => {
        pageCfg.size = document.getElementById('pgSize').value;
        pageCfg.orient = document.getElementById('pgOrient').value;
        if (pageCfg.size === 'custom') {
            pageCfg.w = +document.getElementById('pgW').value || 210;
            pageCfg.h = +document.getElementById('pgH').value || 297;
        } else [pageCfg.w, pageCfg.h] = PAPER[pageCfg.size];
        pageCfg.mt = +document.getElementById('pgMt').value || 0;
        pageCfg.mb = +document.getElementById('pgMb').value || 0;
        pageCfg.ml = +document.getElementById('pgMl').value || 0;
        pageCfg.mr = +document.getElementById('pgMr').value || 0;
        pageCfg.scale = Math.max(30, Math.min(200, +document.getElementById('pgScale').value || 100));
        pageModal().hide();
        applyPageStyle();
    };

    /* ==================== 打印预览 ==================== */
    function resolvePath(obj, path) {
        let cur = obj;
        const parts = String(path).split('.');
        for (const p of parts) {
            if (cur === undefined || cur === null) return undefined;
            cur = cur[p];
        }
        return cur;
    }
    function replaceTokensHtml(s, item, ctx) {
        const re = /\{([^{}]+)\}/g;
        let m, out = '', last = 0;
        while ((m = re.exec(s)) !== null) {
            out += escapeHtml(s.slice(last, m.index));
            last = m.index + m[0].length;
            const token = m[1];
            let val;
            if (token.indexOf('item.') === 0) {
                val = item ? resolvePath(item, token.slice(5)) : undefined;
            } else if (token.indexOf('order.') === 0) {
                val = resolvePath(ctx.order || {}, token.slice(6));
            } else if (Object.prototype.hasOwnProperty.call(ctx, token)) {
                val = ctx[token];
            } else {
                val = undefined;
            }
            out += (val === undefined || val === null)
                ? '<span class="ph-miss">' + escapeHtml(m[0]) + '</span>'
                : escapeHtml(String(val));
        }
        out += escapeHtml(s.slice(last));
        return out;
    }
    function fillCellHtml(text, item, ctx) {
        const s = String(text == null ? '' : text);
        const imgMatch = s.trim().match(/^\{img_(barcode|qrcode):((?:item|order)\.[A-Za-z0-9_.]+)\}$/);
        if (imgMatch) {
            const path = imgMatch[2];
            const scope = path.split('.')[0];
            const val = resolvePath(scope === 'item' ? (item || {}) : (ctx.order || {}), path.slice(scope.length + 1));
            const label = imgMatch[1] === 'barcode' ? '条码' : '二维码';
            return '<div class="img-ph">' + label + '<br>' + escapeHtml(val == null ? '' : String(val)) + '</div>';
        }
        return replaceTokensHtml(s, item, ctx);
    }
    // 明细行扩展：镜像引擎 _Filler 规则——首个含 {item. 的行为模板行，
    // 其下首个含 {total_/{order./{print_date}/{today} 的行为边界
    function expandSheetForPreview(sh, ctx) {
        const st = sh.S;
        const items = ctx.items || [];
        const RC = st.rows.length, CC = st.cols.length;
        const rowText = r => {
            let t = '';
            for (let c = 0; c < CC; c++) t += st.rows[r].cells[c].t;
            return t;
        };
        let tplRow = -1, boundRow = -1; // 0 基
        for (let r = 0; r < RC; r++) {
            const text = rowText(r);
            if (tplRow < 0 && (text.indexOf('{item.') >= 0 || text.indexOf('{img_barcode:item.') >= 0 || text.indexOf('{img_qrcode:item.') >= 0)) {
                tplRow = r;
            } else if (tplRow >= 0 && boundRow < 0 && (
                    text.indexOf('{total_') >= 0 || text.indexOf('{order.') >= 0 ||
                    text.indexOf('{print_date}') >= 0 || text.indexOf('{today}') >= 0)) {
                boundRow = r;
            }
        }
        const rows = [], merges = [], rowHeights = {};
        if (tplRow < 0) {
            for (let r = 0; r < RC; r++) rows.push({ row: r, srcRow: r, item: null });
            eachAnchor(st, (m, r, c) => merges.push({ row: r, col: c, rowspan: m.rs, colspan: m.cs }));
            st.rows.forEach((row, r) => { if (row.hu) rowHeights[r] = row.hu; });
            return { rows, merges, rowHeights };
        }
        const blockSize = boundRow >= 0 ? (boundRow - tplRow) : 1;
        const delta = items.length - blockSize;
        for (let r = 0; r < tplRow; r++) {
            rows.push({ row: r, srcRow: r, item: null });
            if (st.rows[r].hu) rowHeights[r] = st.rows[r].hu;
        }
        items.forEach((item, i) => {
            rows.push({ row: tplRow + i, srcRow: tplRow, item });
            if (st.rows[tplRow].hu) rowHeights[tplRow + i] = st.rows[tplRow].hu;
        });
        for (let r = tplRow + blockSize; r < RC; r++) {
            rows.push({ row: r + delta, srcRow: r, item: null });
            if (st.rows[r].hu) rowHeights[r + delta] = st.rows[r].hu;
        }
        eachAnchor(st, (m, r, c) => {
            if (r < tplRow) merges.push({ row: r, col: c, rowspan: m.rs, colspan: m.cs });
            else if (r >= tplRow + blockSize) merges.push({ row: r + delta, col: c, rowspan: m.rs, colspan: m.cs });
            else if (r === tplRow && m.rs === 1) items.forEach((_, i) => merges.push({ row: tplRow + i, col: c, rowspan: 1, colspan: m.cs }));
        });
        return { rows, merges, rowHeights };
    }
    function eachAnchor(st, fn) {
        for (let r = 0; r < st.rows.length; r++) for (let c = 0; c < st.cols.length; c++) {
            const cell = st.rows[r].cells[c];
            if (!cell.cov && (cell.rs > 1 || cell.cs > 1)) fn(cell, r, c);
        }
    }
    function renderPreviewSheet(sh, ctx) {
        const st = sh.S;
        const expanded = expandSheetForPreview(sh, ctx);
        const covered = new Set(), anchorMap = new Map();
        expanded.merges.forEach(m => {
            anchorMap.set(m.row + ':' + m.col, m);
            for (let i = 0; i < m.rowspan; i++) for (let j = 0; j < m.colspan; j++)
                covered.add((m.row + i) + ':' + (m.col + j));
        });
        let html = '<div class="pv-sheet-name">工作表：' + escapeHtml(sh.name) + '</div>';
        html += '<table class="pv"><colgroup>';
        for (let c = 0; c < st.cols.length; c++) html += '<col style="width:' + wuToPx(st.cols[c].wu) + 'px">';
        html += '</colgroup><tbody>';
        expanded.rows.forEach(ri => {
            const rh = expanded.rowHeights[ri.row];
            html += '<tr' + (rh ? ' style="height:' + huToPx(rh) + 'px"' : '') + '>';
            for (let c = 0; c < st.cols.length; c++) {
                const k = ri.row + ':' + c;
                if (covered.has(k) && !anchorMap.has(k)) continue;
                const m = anchorMap.get(k);
                const cell = st.rows[ri.srcRow].cells[c];
                const css = styleToCssText(cell.s);
                html += '<td' + (m ? ' colspan="' + m.colspan + '" rowspan="' + m.rowspan + '"' : '') +
                    (css ? ' style="' + css + '"' : '') + '>' +
                    fillCellHtml(cell.cov ? '' : cell.t, ri.item, ctx) + '</td>';
            }
            html += '</tr>';
        });
        html += '</tbody></table>';
        return html;
    }
    function renderPreview() {
        const [w, h] = pageDims();
        let inner = '';
        sheets.forEach(sh => { inner += renderPreviewSheet(sh, previewCtx); });
        document.getElementById('previewContent').innerHTML =
            '<div class="paper" style="width:' + w + 'mm;min-height:' + h + 'mm;padding:' +
            pageCfg.mt + 'mm ' + pageCfg.mr + 'mm ' + pageCfg.mb + 'mm ' + pageCfg.ml + 'mm;zoom:' +
            (pageCfg.scale / 100) + ';">' + inner + '</div>';
    }
    function enterPreview() {
        exitEdit();
        const done = () => {
            renderPreview();
            document.getElementById('editorArea').style.display = 'none';
            document.getElementById('previewArea').style.display = 'block';
        };
        if (previewCtx) { done(); return; }
        WMS.api.get(PREVIEW_URL).then(function(res) {
            previewCtx = res.context || {};
            done();
        }).catch(function(err) {
            toast(escapeHtml(err.message || '预览数据加载失败'), 'error');
        });
    }
    document.getElementById('btnPreview').onclick = enterPreview;
    document.getElementById('btnExitPreview').onclick = () => {
        document.getElementById('previewArea').style.display = 'none';
        document.getElementById('editorArea').style.display = '';
    };
    document.getElementById('btnDoPrint').onclick = () => window.print();

    /* ==================== 初始化 ==================== */
    buildPlaceholders();
    applyPageStyle();
    loadGrid();

    // 冒烟测试钩子（生产无副作用，仅供自动化测试读取内部状态）
    window.__tplEditor = {
        getS: () => S,
        getSheets: () => sheets,
        getActiveIdx: () => activeIdx,
    };
})();
