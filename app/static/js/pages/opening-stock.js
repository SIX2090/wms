const OPENING_DOC = window.__OPENING_DOC__ || null;
// BUG-2026-09-16-012：物料不再整库内嵌（Material.query.all() 全量塞页面，
// 物料上千时首屏卡死，R1）。改为「服务端搜索 + 本地缓存」：
//   · 联想：/api/material/search?keyword= 防抖 200ms 拉取（最多返回服务端上限条）；
//   · 粘贴导入：/opening_stock/materials/lookup 按编码批量预热缓存；
//   · 选中/解析一律查缓存（payload 与移动端同一构造器 api_material_payload）。
const materialCache = new Map();      // id(Number) -> 物料 payload
const materialCodeIndex = new Map();  // code(小写) -> 物料 payload
function cacheMaterial(m) {
    if (!m || m.id === null || m.id === undefined) return;
    materialCache.set(Number(m.id), m);
    materialCodeIndex.set(String(m.code || '').toLowerCase(), m);
}
function findMaterialByCode(code) {
    return materialCodeIndex.get(String(code || '').trim().toLowerCase()) || null;
}
let rows = existingRows.length ? existingRows.slice() : [];
let activeCodeInput = null;
const gridBody = document.getElementById('openingGridBody');
const materialMenu = document.getElementById('materialMenu');
function emptyRow() {
    return {material_id: '', warehouse_id: '', warehouse_name: '', material_code: '', material_name: '', spec: '', unit: '', quantity: '', price: '', remark: '', location: ''};
}

function amountOf(row) {
    const quantity = Number(row.quantity || 0);
    const price = Number(row.price || 0);
    return quantity * price;
}

function warehouseOptionsHtml(selectedId) {
    const opts = ['<option value="">请选择仓库</option>'];
    warehouseOptions.forEach(w => {
        const selected = String(w.id) === String(selectedId || '') ? ' selected' : '';
        opts.push(`<option value="${w.id}"${selected}>${escapeHtml(w.name)}</option>`);
    });
    return opts.join('');
}

function renderRows() {
    closeMaterialMenu();
    if (rows.length === 0) {
        gridBody.innerHTML = `<tr><td colspan="${GRID_COLSPAN}" class="text-center text-muted" style="padding:18px;">暂无明细，请点击"添加物料"开始录入</td></tr>`;
        syncCheckAllState();
        updateTotal();
        return;
    }
    gridBody.innerHTML = rows.map((row, index) => `
        <tr data-index="${index}">
            <td class="text-center"><input type="checkbox" class="opening-row-check" data-index="${index}"${selectedFlags[index] ? ' checked' : ''} onchange="onRowCheckToggle(${index}, this.checked)" aria-label="勾选第 ${index + 1} 行"></td>
            <td class="row-no">${index + 1}</td>
            <td><select class="form-select form-select-sm" onchange="updateField(${index}, 'warehouse_id', this.value); updateField(${index}, 'warehouse_name', this.options[this.selectedIndex]?.text || '');">${warehouseOptionsHtml(row.warehouse_id)}</select></td>
            ${LOCATION_ENABLED ? `<td><input data-field="location" value="${escapeHtml(row.location || '')}" placeholder="库位" oninput="updateField(${index}, 'location', this.value);"></td>` : ''}
            <td class="code-cell"><input data-field="material_code" value="${escapeHtml(row.material_code || '')}" autocomplete="off" oninput="updateField(${index}, 'material_code', this.value); showMaterialMenu(this, ${index});" onfocus="showMaterialMenu(this, ${index});"></td>
            <td><input value="${escapeHtml(row.material_name || '')}" readonly></td>
            <td><input value="${escapeHtml(row.spec || '')}" readonly></td>
            <td><input value="${escapeHtml(row.unit || '')}" readonly></td>
            <td class="num"><input type="number" min="0" step="0.0001" data-field="quantity" value="${escapeHtml(row.quantity ?? '')}" oninput="updateField(${index}, 'quantity', this.value);"></td>
            <td class="num"><input type="number" min="0" step="0.0001" data-field="price" value="${escapeHtml(row.price ?? '')}" oninput="updateField(${index}, 'price', this.value);"></td>
            <td class="amount"><input value="${formatMoney(amountOf(row), false)}" readonly></td>
            <td><input data-field="remark" value="${escapeHtml(row.remark || '')}" oninput="updateField(${index}, 'remark', this.value);"></td>
            <td><div class="action-cell"><button class="icon-btn" type="button" onclick="insertRowAfter(${index})" title="插入行"><i class="bi bi-plus-circle"></i></button><button class="icon-btn danger" type="button" onclick="deleteRow(${index})" title="${row.line_id ? '删除本行（已建账，将立即回冲库存）' : '删除本行（尚未保存）'}"><i class="bi bi-trash"></i></button></div></td>
        </tr>
    `).join('');
    syncCheckAllState();
    updateTotal();
    // P1-D：注意——这里**故意不**落草稿。
    // renderRows() 不只在用户编辑时跑，它在页面加载、恢复草稿、服务端行回填时
    // 都会跑。若在这里无条件 scheduleDraftSave()，打开一张已建账的单据就会
    // 立刻写出一份"草稿"：用户什么都没改，刷新却提示"有未保存草稿"；更糟的是
    // 保存成功后 clearDraft() 刚清掉，紧随其后的 700ms 跳转重新加载页面又把它
    // 写回来（实测复现）。因此落草稿一律由"用户意图"驱动（updateField / addRow /
    // insertRowAfter / deleteRow / clearEntryRows / 表头输入 / 粘贴导入），
    // 这些入口各自显式调用 scheduleDraftSave()。
}

// ======================================================================
// P1-D 录入草稿防丢
//
// 问题：期初录入是个"扫几十上百行"的慢活。手机端连着扫码枪扫到一半刷新、
// 误点返回列表、浏览器崩了、切去别处查一下料——回来录入全没了，只能重扫。
// 期初又是账的起点，重录成本极高且容易录漏。
//
// 方案：把**当前录入网格**按单据维度存进 localStorage，页面加载时若检测到
// 未保存草稿则显形提示条，用户点「恢复草稿」才真的覆盖——不自动应用，
// 避免"我明明清空了它怎么又自己回来了"这种更吓人的体验。
//
// 口径细节：
//   · 作用域按单据：新建页 key = 'new'，编辑页 key = 单据 id。切到别的单
//     不会串草稿（编辑页草稿里那些行属于那张单，不该跑到另一张单去）。
//   · 只存"用户改过"的行：全空行不入库，避免刚打开页面就凭空多出一行空白。
//   · 已建账行（有 line_id）也存：用户在详情页改了数量但没保存就刷新，
//     这些改动同样会丢，必须一起兜住。
//   · 保存成功后清除：草稿的语义是"未落库的改动"，落库了就该消失。
//   · 配额/隐私模式兜底：localStorage 可能不可用（无痕模式、配额满），
//     所有读写都包 try/catch，失败静默降级——草稿是锦上添花，不能因此报错。
// ======================================================================
const DRAFT_KEY_PREFIX = 'wms.opening_stock.draft.';
const DRAFT_SAVE_DEBOUNCE_MS = 400;
// 草稿作用域：新建页是 'new'，编辑页是该单据 id
const DRAFT_SCOPE = OPENING_DOC && OPENING_DOC.id ? String(OPENING_DOC.id) : 'new';
const DRAFT_KEY = DRAFT_KEY_PREFIX + DRAFT_SCOPE;
let draftSaveTimer = null;
// 恢复草稿时置位，避免恢复动作本身又触发一轮保存
let draftRestoring = false;

/** 判断一行是否"用户动过"（全空行不存）。 */
function isMeaningfulRow(row) {
    return !!(row.material_id || row.material_code || row.quantity ||
              row.price || row.remark || row.warehouse_id ||
              (row.location || '').trim());
}

/** 只把动过的行写进草稿（避免把整张表的空行也塞进去撑爆配额）。 */
function collectDraftRows() {
    return rows.filter(isMeaningfulRow).map(row => ({
        line_id: row.line_id ?? null,
        material_id: row.material_id,
        warehouse_id: row.warehouse_id,
        warehouse_name: row.warehouse_name,
        material_code: row.material_code,
        material_name: row.material_name,
        spec: row.spec,
        unit: row.unit,
        quantity: row.quantity,
        price: row.price,
        remark: row.remark,
        location: row.location,
    }));
}

/** 表头三件套：日期 / 单据仓库 / 备注。存在草稿里一起恢复。 */
function collectDraftHeader() {
    const read = id => {
        const el = document.getElementById(id);
        return el ? el.value : '';
    };
    return {
        date: read('headerDocDate'),
        warehouse_id: read('headerWarehouse'),
        remark: read('headerRemark'),
    };
}

function readDraft() {
    try {
        const raw = localStorage.getItem(DRAFT_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || !Array.isArray(parsed.rows) || !parsed.rows.length) return null;
        return parsed;
    } catch (e) {
        // 无痕模式 / 数据被外部改坏 / 配额异常：当作没有草稿
        return null;
    }
}

/** 立即落盘（供 debounce 与 beforeunload 共用）。 */
function persistDraftNow() {
    try {
        const draftRows = collectDraftRows();
        const header = collectDraftHeader();
        if (!draftRows.length) {
            // 全清空了：草稿本身也该消失，否则下次进来会提示"有草稿"却恢复出空表
            localStorage.removeItem(DRAFT_KEY);
            return;
        }
        localStorage.setItem(DRAFT_KEY, JSON.stringify({
            scope: DRAFT_SCOPE,
            saved_at: new Date().toISOString(),
            header: header,
            rows: draftRows,
        }));
    } catch (e) {
        // 写失败（配额满/隐私模式）静默降级，不打断录入
    }
}

/** 防抖落盘：连续敲键盘时不每字符都写一次 localStorage。 */
function scheduleDraftSave() {
    if (draftRestoring) return;
    if (draftSaveTimer) clearTimeout(draftSaveTimer);
    draftSaveTimer = setTimeout(persistDraftNow, DRAFT_SAVE_DEBOUNCE_MS);
}

function clearDraft() {
    if (draftSaveTimer) { clearTimeout(draftSaveTimer); draftSaveTimer = null; }
    try {
        localStorage.removeItem(DRAFT_KEY);
    } catch (e) {
        // 忽略：清不掉也不影响主流程
    }
}

/** 草稿保存时间的可读文案（"3 分钟前"）。 */
function draftSavedAgoText(savedAt) {
    const ts = Date.parse(savedAt || '');
    if (isNaN(ts)) return '';
    const minutes = Math.floor((Date.now() - ts) / 60000);
    if (minutes < 1) return '刚刚';
    if (minutes < 60) return minutes + ' 分钟前';
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return hours + ' 小时前';
    return Math.floor(hours / 24) + ' 天前';
}

/**
 * 页面加载时检查草稿并显形提示条。
 *
 * 只在"当前网格没有任何有效行"时提示——如果本单在服务端已有明细（编辑页）
 * 或用户已经开始录入，说明他手上就是最新的，再弹恢复提示纯属打扰。
 */
function checkDraftOnLoad() {
    const banner = document.getElementById('draftBanner');
    if (!banner) return;
    if (collectDraftRows().length) return;   // 当前已有内容，不打扰

    const draft = readDraft();
    if (!draft) return;

    const label = document.getElementById('draftBannerText');
    if (label) {
        const ago = draftSavedAgoText(draft.saved_at);
        label.textContent = '检测到本单有未保存的录入草稿：'
            + draft.rows.length + ' 行' + (ago ? '（' + ago + '保存）' : '');
    }
    banner.hidden = false;
}

/** 「恢复草稿」：把草稿行灌回网格。注意已建账行的 line_id 要保留，
 *  否则恢复后再保存会被后端当成新增行（同一物料出两行）。 */
function restoreDraft() {
    const draft = readDraft();
    if (!draft) {
        showToast('草稿已不存在，可能已在其他标签页清除', 'warning');
        hideDraftBanner();
        return;
    }
    draftRestoring = true;
    try {
        rows = draft.rows.map(item => ({
            line_id: item.line_id ?? null,
            material_id: item.material_id || '',
            warehouse_id: item.warehouse_id || '',
            warehouse_name: item.warehouse_name || '',
            material_code: item.material_code || '',
            material_name: item.material_name || '',
            spec: item.spec || '',
            unit: item.unit || '',
            quantity: item.quantity ?? '',
            price: item.price ?? '',
            remark: item.remark || '',
            location: item.location || '',
        }));
        selectedFlags = [];
        syncSelectedFlags(rows.length);
        renderRows();
        // 表头三件套一并回填（日期/单据仓库/备注）
        const head = draft.header || {};
        const setVal = (id, value) => {
            const el = document.getElementById(id);
            if (el && value !== undefined && value !== null) el.value = value;
        };
        if (head.date !== undefined && head.date !== null) {
            setWmsDateInputValue(document.getElementById('headerDocDate'), head.date);
        }
        setVal('headerWarehouse', head.warehouse_id);
        setVal('headerRemark', head.remark);
        hideDraftBanner();
        showToast('已恢复 ' + rows.length + ' 行草稿，记得点「保存」才会落库', 'success', 4200);
    } finally {
        draftRestoring = false;
    }
}

/** 「丢弃并清除」：删掉草稿，网格保持现状。 */
function discardDraft() {
    clearDraft();
    hideDraftBanner();
    showToast('草稿已丢弃', 'info', 2400);
}

function hideDraftBanner() {
    const banner = document.getElementById('draftBanner');
    if (banner) banner.hidden = true;
}

// ---- 批量删行（勾选）----
// selectedFlags 与 rows 同下标，保存"这一行是否被勾选"。
// 不用 DOM 查询读勾选态：renderRows() 会整体重建 tbody，DOM 态随之下线，
// 必须把勾选态提到数据层才能在重渲染（改数量、加行、插入行）后不丢。
let selectedFlags = [];
const checkAllBox = document.getElementById('openingCheckAll');

// 行数变化（增删/插入/重载）后把勾选数组对齐到新长度，多退少补。
function syncSelectedFlags(rowCount) {
    if (selectedFlags.length > rowCount) selectedFlags.length = rowCount;
    while (selectedFlags.length < rowCount) selectedFlags.push(false);
}

function onRowCheckToggle(index, checked) {
    selectedFlags[index] = !!checked;
    syncCheckAllState();
}

// 表头全选框的 checked/indeterminate 随行勾选态联动（半选态也要体现）
function syncCheckAllState() {
    if (!checkAllBox) return;
    const enabled = rows.map((_, i) => i);
    const checkedCount = enabled.filter(i => selectedFlags[i]).length;
    checkAllBox.checked = enabled.length > 0 && checkedCount === enabled.length;
    checkAllBox.indeterminate = checkedCount > 0 && checkedCount < enabled.length;
    // 勾选计数提示：让用户明确"已勾几行"，避免点删除时才发现勾错
    const hint = document.getElementById('selectedHint');
    if (hint) {
        hint.textContent = checkedCount ? `已勾选 ${checkedCount} 行` : '未勾选';
        hint.className = checkedCount
            ? 'ms-auto text-danger small align-self-center'
            : 'ms-auto text-muted small align-self-center';
    }
}

function onCheckAllToggle(checked) {
    selectedFlags = rows.map(() => !!checked);
    renderRows();
}

if (checkAllBox) {
    checkAllBox.addEventListener('change', function() { onCheckAllToggle(this.checked); });
}

// 批量删除勾选的明细行。
// 分两条路径，语义必须说清楚给用户：
//   · 已保存行（有 line_id）→ 调后端批量接口，立即物理删除 + 库存回冲；
//   · 未保存行（刚加、还没存过）→ 只从录入网格移除，不涉及库存。
// 混选时两条路径都走，并在确认框里分别报出数量，避免用户误以为"删了但没生效"。
function batchDeleteSelectedRows() {
    if (!rows.length) {
        showToast('当前没有可删除的明细行', 'info');
        return;
    }
    const selectedIndexes = rows.map((_, i) => i).filter(i => selectedFlags[i]);
    if (!selectedIndexes.length) {
        showToast('请先勾选要删除的明细行', 'warning');
        return;
    }

    const savedLines = selectedIndexes.filter(i => rows[i].line_id);
    const unsavedLines = selectedIndexes.filter(i => !rows[i].line_id);

    let confirmMsg = `确定删除勾选的 ${selectedIndexes.length} 行明细吗？`;
    if (savedLines.length) {
        confirmMsg += `\n其中 ${savedLines.length} 行已建账，将立即从库存中扣回，此操作不可恢复。`;
    }
    if (unsavedLines.length) {
        confirmMsg += `\n另有 ${unsavedLines.length} 行尚未保存，仅从当前录入中移除。`;
    }
    if (!confirm(confirmMsg)) return;

    // 未保存行直接在本地移除（不碰后端）
    if (!savedLines.length) {
        removeRowsAt(selectedIndexes);
        showToast(`已移除 ${selectedIndexes.length} 行未保存的明细`, 'success');
        return;
    }

    if (!OPENING_DOC) {
        // 理论不可达：没有单据就不该有 line_id。兜底按未保存处理，避免打到不存在的单据 id。
        removeRowsAt(selectedIndexes);
        showToast(`已移除 ${selectedIndexes.length} 行未保存的明细`, 'success');
        return;
    }

    const lineIds = savedLines.map(i => rows[i].line_id);
    WMS.api.post('/opening_stock/' + OPENING_DOC.id + '/lines/delete', { line_ids: lineIds })
        .then(function(data) {
            if (data && data.status === 'success') {
                // 已保存行已被后端删除，本地同步摘掉；未保存行一并移除
                removeRowsAt(selectedIndexes);
                let msg = data.msg || '明细行已删除';
                if (unsavedLines.length) msg += `；另移除 ${unsavedLines.length} 行未保存明细`;
                showToast(msg, 'success', 4200);
            } else {
                showToast((data && data.msg) || '删除失败', 'danger', 4200);
            }
        })
        .catch(function(error) {
            showToast('删除失败：' + (error && error.message ? error.message : '未知错误'), 'danger', 4200);
        });
}

// 按下标数组删除本地行（从后往前删，避免下标位移错杀）
function removeRowsAt(indexes) {
    indexes.slice().sort((a, b) => b - a).forEach(i => {
        rows.splice(i, 1);
        selectedFlags.splice(i, 1);
    });
    syncSelectedFlags(rows.length);
    renderRows();
}

function updateField(index, field, value) {
    rows[index][field] = value;
    if (field === 'quantity' || field === 'price') {
        const tr = gridBody.querySelector(`tr[data-index="${index}"]`);
        if (tr) tr.querySelector('.amount input').value = formatMoney(amountOf(rows[index]), false);
        updateTotal();
    }
    // P1-D：直接改字段不走 renderRows()，要单独触发草稿保存
    scheduleDraftSave();
}

function addRow() {
    rows.push(emptyRow());
    syncSelectedFlags(rows.length);
    renderRows();
    // P1-D：加行是用户意图 → 落草稿
    scheduleDraftSave();
}

function insertRowAfter(index) {
    rows.splice(index + 1, 0, emptyRow());
    // 勾选态按下标对齐：插入点之后的勾选要跟着行往后挪，否则会误勾到相邻行
    selectedFlags.splice(index + 1, 0, false);
    syncSelectedFlags(rows.length);
    renderRows();
    // P1-D：插行是用户意图 → 落草稿
    scheduleDraftSave();
}

// 行内删除图标：删除单行。
// BUG-2026-09-16-005：原先这里只做 rows.splice()，删的是**前端数组**——
//   已建账的行必须再点一次「保存」才会由后端差集回冲落库。用户点完删除图标
//   看见行消失了，以为已删除就直接离开页面，结果下次打开该行又在（且库存未回冲）。
//   界面也没有任何提示，属"静默失效"。
// 现按行是否已建账分流，与 batchDeleteSelectedRows 同一口径：
//   · 已建账行（有 line_id）→ 走 /lines/delete 立即物理删除 + 库存回冲；
//   · 未保存行 → 仅从录入网格移除，并明确提示"尚未保存"。
function deleteRow(index) {
    const row = rows[index];
    if (!row) return;

    const isSaved = !!(row.line_id);
    const label = row.material_name || row.material_code || `第 ${index + 1} 行`;

    if (isSaved && OPENING_DOC) {
        const confirmed = confirm(
            `确定删除「${label}」吗？\n该行已建账，将立即从库存中扣回，此操作不可恢复。`
        );
        if (!confirmed) return;
        WMS.api.post('/opening_stock/' + OPENING_DOC.id + '/lines/delete', {
            line_ids: [row.line_id],
        })
            .then(function(data) {
                if (data && data.status === 'success') {
                    rows.splice(index, 1);
                    selectedFlags.splice(index, 1);
                    syncSelectedFlags(rows.length);
                    renderRows();
                    // P1-D：删行已落库成功 → 该行不该继续留在草稿里
                    scheduleDraftSave();
                    showToast(data.msg || '明细行已删除，库存已回冲', 'success', 4200);
                } else {
                    showToast((data && data.msg) || '删除失败', 'danger', 4200);
                }
            })
            .catch(function(error) {
                showToast(
                    '删除失败：' + (error && error.message ? error.message : '未知错误'),
                    'danger', 4200
                );
            });
        return;
    }

    // 未保存行：本地移除即可，但必须让用户知道"还没落库、需保存才生效"。
    rows.splice(index, 1);
    selectedFlags.splice(index, 1);
    syncSelectedFlags(rows.length);
    renderRows();
    // P1-D：删行是用户意图 → 落草稿（否则刷新后删掉的行又回来了）
    scheduleDraftSave();
    showToast(`已移除「${label}」（尚未保存，点「保存」后才生效）`, 'info', 3600);
}

// 顶部工具栏「删除」：清空当前录入的全部明细行（仅未保存内容；已建账记录不受影响）。
function clearEntryRows() {
    if (!rows.length) {
        showToast('当前没有可清空的明细行', 'info');
        return;
    }
    if (!confirm('确定清空当前录入的全部明细行吗？（未保存的内容将丢失，已建账记录不受影响）')) return;
    rows = [];
    selectedFlags = [];
    renderRows();
    // P1-D：这是用户明确的"不要了"，草稿要跟着一起清——否则下次进来
    // 提示"有草稿"再恢复出来，就变成了"清空没生效"。
    clearDraft();
    hideDraftBanner();
}

function copyPreviousRow() {
    const filled = rows.filter(row => row.material_id);
    if (!filled.length) {
        showToast('没有可复制的上一行', 'warning');
        return;
    }
    rows.push({...filled[filled.length - 1], remark: ''});
    syncSelectedFlags(rows.length);
    renderRows();
    // P1-D：复制上一行是用户意图 → 落草稿
    scheduleDraftSave();
}

function resetDocument() {
    // 新建：清空明细并回到"未取号"状态（保存时才生成单号）
    rows = [];
    selectedFlags = [];
    renderRows();
    // P1-D：点「新增」是明确的"这张单不要了"，草稿一并清掉
    clearDraft();
    hideDraftBanner();
    if (typeof goToNewDoc === 'function') goToNewDoc();
}

// ARCH-OS-DOC-01：首/上/下/末 真实导航。
// 详情页路径形如 /opening_stock/12，后端 /api/document_navigation/opening_stock
// 按当前 id 返回 first/prev/next/last_id；新建页（无 id）首张=first、末张=last。
function navigateOpeningDoc(target) {
    if (!window.WMS || !WMS.api) return;
    const currentId = OPENING_DOC && OPENING_DOC.id;
    const query = currentId ? '?current_id=' + encodeURIComponent(currentId) : '';
    WMS.api.get('/api/document_navigation/opening_stock' + query)
        .then(function(data) {
            const payload = (data && data.data) ? data.data : data;
            let targetId = payload ? payload[target + '_id'] : null;
            if (!payload) {
                showToast('单据导航加载失败', 'danger', 3600);
                return;
            }
            const isNewPage = !OPENING_DOC;
            if (!targetId && isNewPage) {
                // 新建页没有当前单据：首/末张直接取两端，上/下张给末/首张（与 app.js 同款兜底）
                if (target === 'prev') targetId = payload.last_id;
                else if (target === 'next') targetId = payload.first_id;
            }
            if (!targetId) {
                if (target === 'first' || target === 'last') {
                    showToast(payload.total ? '没有符合条件的单据' : '暂无期初库存单据', 'warning');
                } else if (target === 'prev') {
                    showToast('已经是首张单据', 'info');
                } else {
                    showToast('已经是末张单据', 'info');
                }
                return;
            }
            window.location.href = '/opening_stock/' + targetId;
        })
        .catch(function(error) {
            showToast('单据导航失败：' + (error && error.message ? error.message : '未知错误'), 'danger', 3600);
        });
}

// 跳转到新建页（清空当前编辑上下文）
function goToNewDoc() {
    if (window.location.pathname.replace(/\/+$/, '') !== '/opening_stock/add') {
        window.location.href = '/opening_stock/add';
    }
}

// 删除当前单据（物理删除 + 库存回冲，后端负责）
function deleteCurrentDoc() {
    if (!OPENING_DOC) {
        showToast('当前是新建单据，无需删除', 'info');
        return;
    }
    if (!confirm('确定删除单据 ' + (OPENING_DOC.doc_no || '') + ' 吗？\n该单所有明细的期初数量将从库存中扣回，此操作不可恢复。')) return;
    WMS.api.post('/opening_stock/' + OPENING_DOC.id + '/delete')
        .then(function(data) {
            if (data && data.status === 'success') {
                showToast(data.msg || '单据已删除', 'success');
                setTimeout(function() { window.location.href = '/opening_stock'; }, 800);
            } else {
                showToast((data && data.msg) || '删除失败', 'danger', 4200);
            }
        })
        .catch(function(error) {
            showToast('删除失败：' + (error && error.message ? error.message : '未知错误'), 'danger', 4200);
        });
}

// BUG-2026-09-16-012：联想改服务端搜索——防抖 200ms + 序号防竞态
//（后发请求先到时丢弃旧结果，与手机端 searchMaterialSuggestions 同思路）。
let materialSearchSeq = 0;
let materialSearchTimer = null;

function closeMaterialMenu() {
    materialSearchSeq++;
    if (materialSearchTimer) clearTimeout(materialSearchTimer);
    materialSearchTimer = null;
    activeCodeInput = null;
    materialMenu.hidden = true;
}

function renderMaterialMenuItems(matches, index) {
    materialMenu.innerHTML = matches.length ? matches.map(item => `
        <div class="material-menu-item" onclick="selectMaterial(${index}, ${item.id})">
            <span class="code">${escapeHtml(item.code || '')}</span>
            <span class="name">${escapeHtml(item.name || '')}</span>
            <span class="meta">规格：${escapeHtml(item.spec || '-')}</span>
            <span class="meta">单位：${escapeHtml(item.unit || '-')}</span>
            <span class="meta">库存：${escapeHtml(item.stock ?? 0)}</span>
        </div>
    `).join('') : '<div class="material-menu-item">没有匹配物料</div>';
    if (matches.length >= 100) materialMenu.insertAdjacentHTML('beforeend', '<div class="text-muted small p-2">本次显示前100条候选，请细化编码 / 名称 / 规格继续查找。</div>');
}

function showMaterialMenu(input, index) {
    const seq = ++materialSearchSeq;
    if (materialSearchTimer) clearTimeout(materialSearchTimer);
    materialSearchTimer = null;
    activeCodeInput = {input, index};
    WMS.positionDropdown(input, materialMenu, {minWidth: 520, gap: 4});
    materialMenu.hidden = false;
    const kw = String(input.value || '').trim();
    if (!kw) {
        // 空关键字不再展示"全部物料前 30 条"（整库内嵌已移除）——提示输入关键字
        materialMenu.innerHTML = '<div class="material-menu-item">输入编码 / 名称 / 规格关键字搜索物料</div>';
        return;
    }
    materialMenu.innerHTML = '<div class="material-menu-item">搜索中…</div>';
    const isCurrent = () => seq === materialSearchSeq && activeCodeInput &&
        activeCodeInput.input === input && activeCodeInput.index === index &&
        input.isConnected !== false && String(input.value || '').trim() === kw;
    materialSearchTimer = setTimeout(function() {
        if (!isCurrent()) return;
        // 模糊联想仅显示服务端返回的前 100 个候选，不作为全量档案。
        WMS.api.get('/api/material/search?keyword=' + encodeURIComponent(kw))
            .then(function(data) {
                if (!isCurrent()) return;
                if (!Array.isArray(data)) throw new Error('物料搜索响应格式无效');
                const items = data;
                items.forEach(cacheMaterial);
                renderMaterialMenuItems(items, index);
            })
            .catch(function() {
                if (!isCurrent()) return;
                materialMenu.innerHTML = '<div class="material-menu-item">搜索失败，请重试</div>';
            });
    }, 200);
}

function selectMaterial(index, materialId) {
    const material = materialCache.get(Number(materialId));
    if (!material) return;
    rows[index] = {
        ...rows[index],
        material_id: material.id,
        material_code: material.code || '',
        material_name: material.name || '',
        spec: material.spec || '',
        unit: material.unit || '',
        price: rows[index].price || material.price || 0,
    };
    closeMaterialMenu();
    renderRows();
    // P1-D：选中物料是用户意图 → 落草稿
    scheduleDraftSave();
}

function collectItems() {
    return rows
        .filter(row => row.material_id || row.material_code || row.quantity || row.price || row.remark || row.warehouse_id)
        .map(row => ({
            material_id: row.material_id,
            warehouse_id: row.warehouse_id,
            quantity: row.quantity,
            price: row.price,
            remark: row.remark,
            location: (row.location || '').trim(),
        }));
}

// 表头日期：作为所有明细行的默认建账日期（缺省今天）
function getHeaderDocDate() {
    return document.getElementById('headerDocDate')?.value || '';
}

function saveDocument() {
    const headerWarehouseId = document.getElementById('headerWarehouse')?.value;
    const items = collectItems();
    if (!items.length) {
        showToast('请至少录入一行期初库存', 'warning');
        return;
    }
    // AI-OS-MW-001: 表头仓库为空时，自动使用明细中已选仓库
    if (!headerWarehouseId) {
        const uniqueWarehouses = Array.from(new Set(items.map(item => String(item.warehouse_id || '')).filter(Boolean)));
        if (uniqueWarehouses.length === 0) {
            showToast('请选择表头仓库或在明细中为每行选择仓库', 'warning');
            return;
        }
        if (uniqueWarehouses.length > 1) {
            showToast('明细涉及多个仓库，请先在表头选择仓库', 'warning');
            return;
        }
        items.forEach(item => { item.warehouse_id = uniqueWarehouses[0]; });
    } else {
        // 表头有仓库时：未指定明细行的仓库自动使用表头仓库
        items.forEach(item => { if (!item.warehouse_id) item.warehouse_id = headerWarehouseId; });
    }
    // BUG-2026-09-16-011：库位管理启用时库位必填（AGENTS.md 规则二，与入库单同口径）。
    // 仓库兜底解析之后再校验，确保每行最终都有明确归属。
    if (LOCATION_ENABLED) {
        const missingLocRows = [];
        rows.forEach((row, i) => {
            const isEmptyRow = !(row.material_id || row.material_code || row.quantity || row.price || row.remark || row.warehouse_id);
            if (!isEmptyRow && !(row.location || '').trim()) missingLocRows.push(i + 1);
        });
        if (missingLocRows.length) {
            showToast(`库位管理已启用，第 ${missingLocRows.slice(0, 5).join('、')} 行${missingLocRows.length > 5 ? ' 等' : ''} 未填写库位，请补全后再保存`, 'danger', 4200);
            return;
        }
    }
    // FIX-OS-DATE-001: 表头日期落到每行明细（后端 _parse_opening_stock_date 逐行解析）
    const headerDate = getHeaderDocDate();
    if (headerDate) {
        items.forEach(item => { if (!item.date) item.date = headerDate; });
    }
    // BUG-2026-09-15-006: 表头备注接通保存——作为各行明细的默认备注（行内已填备注的行不受影响）
    const headerRemark = (document.getElementById('headerRemark')?.value || '').trim();
    if (headerRemark) {
        items.forEach(item => { if (!item.remark) item.remark = headerRemark; });
    }
    // ARCH-OS-DOC-01：走单据级保存接口。
    // 编辑已有单据时带 doc_id，后端按 (物料,仓库) upsert 并把消失的行回冲删除；
    // 新建时 doc_id 为空，后端取号建单头（首/上/下/末 才能找到它）。
    const payload = { items };
    if (OPENING_DOC) payload.doc_id = OPENING_DOC.id;
    if (headerDate) payload.date = headerDate;
    if (headerWarehouseId) payload.warehouse_id = headerWarehouseId;
    payload.remark = headerRemark;
    WMS.api.post('/opening_stock/save', payload)
        .then(data => {
            if (data && data.status === 'success') {
                // P1-D：落库成功 → 草稿使命结束，必须清掉。
                // 不清的话下次进这张单会提示"有未保存草稿"，恢复出来一堆
                // 已经被服务端合并过的行，用户会以为保存没生效。
                clearDraft();
                showToast(data.msg || '保存成功', 'success');
                // 新建成功后跳到详情页，这样首/上/下/末 和删除按钮都立即可用
                const newId = data.doc_id;
                setTimeout(() => {
                    if (newId) window.location.href = '/opening_stock/' + newId;
                    else window.location.reload();
                }, 700);
            } else {
                showToast((data && data.msg) || '保存失败', 'danger', 4200);
            }
        })
        .catch(error => showToast('保存失败：' + error.message, 'danger', 4200));
}

function showPasteModal() {
    invalidatePasteLookup();
    document.getElementById('pasteImportText').value = '';
    document.getElementById('pasteImportFeedback').textContent = '';
    // FIX-OS-DATE-001: 默认沿用表头日期，避免导入时丢失用户选择的建账日期
    setWmsDateInputValue(document.getElementById('pasteDocDate'), getHeaderDocDate());
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('pasteImportModal'));
    modal.show();
}

// 解析多行粘贴文本为明细行。支持 Tab / 英文逗号分隔，空列可省。
// FIX-OS-DATE-001: 支持可选的"日期"列（第 6 列），格式 YYYY-MM-DD，非法则该行回落默认日期。
// BUG-2026-09-16-004：兼容「本页导出」的 CSV 重新粘贴/导入——
//   ① 支持带引号的单元格（Excel/WPS 另存 CSV 均为 "a","b" 形式）与其中的 "" 转义；
//   ② 自动跳过表头行（首列是「仓库」/「仓库编码」）；
//   ③ 若检测到导出格式的 9 列（仓库编码,物料编码,物料名称,规格,单位,数量,单价,备注,日期），
//      按导出列序取值，保证"导出→改→粘贴导入"闭环；否则维持原有 6 列宽松解析。
function splitCsvLine(line) {
    // 手写 CSV 切分：支持双引号包裹、"" 转义、引号内逗号，同时兼容无引号的裸 Tab/逗号文本。
    const cells = [];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i += 1) {
        const ch = line[i];
        if (inQuotes) {
            if (ch === '"') {
                if (line[i + 1] === '"') { cur += '"'; i += 1; } else { inQuotes = false; }
            } else {
                cur += ch;
            }
        } else if (ch === '"') {
            inQuotes = true;
        } else if (ch === ',' || ch === '\t') {
            cells.push(cur.trim());
            cur = '';
        } else {
            cur += ch;
        }
    }
    cells.push(cur.trim());
    return cells;
}

function parsePasteLines(text, defaultDate) {
    const result = { items: [], errors: [] };
    const rawLines = String(text || '').split(/\r?\n/).map(l => l.replace(/\r/g, '')).filter(l => l.trim() !== '');
    // 跳过表头行：首列（去引号后）为「仓库」或「仓库编码」即判定表头。
    let startIndex = 0;
    if (rawLines.length) {
        const headFirst = splitCsvLine(rawLines[0])[0] || '';
        const headClean = headFirst.replace(/^"|"$/g, '').trim();
        if (headClean === '仓库' || headClean === '仓库编码' || headClean === '物料编码') {
            startIndex = 1;
        }
    }
    const lines = rawLines.slice(startIndex);
    lines.forEach((line, idx) => {
        const parts = splitCsvLine(line);
        // 9 列 = 本页导出格式（仓库编码,物料编码,物料名称,规格,单位,数量,单价,备注,日期）；
        // 其余按宽松的 6 列（仓库,编码,数量,单价,备注,日期）。
        const isExportFormat = parts.length >= 9;
        const whCode = parts[0];
        const code = parts[1];
        const quantity = isExportFormat ? parts[5] : parts[2];
        const price = isExportFormat ? parts[6] : parts[3];
        const remark = isExportFormat ? parts[7] : parts[4];
        const dateRaw = isExportFormat ? parts[8] : parts[5];
        const lineNo = idx + 1;
        if (!code) {
            result.errors.push(`第 ${lineNo} 行：缺物料编码`);
            return;
        }
        // BUG-2026-09-16-012：物料解析改查本地缓存（confirmPasteImport 已先走
        // /opening_stock/materials/lookup 批量预热），不再依赖整库内嵌的 materialData。
        const material = findMaterialByCode(code);
        if (!material) {
            result.errors.push(`第 ${lineNo} 行：物料编码 [${code}] 不存在`);
            return;
        }
        let wh = null;
        if (whCode) {
            wh = warehouseOptions.find(w => String(w.id) === String(whCode) || String(w.name).toLowerCase().includes(String(whCode).toLowerCase()));
            if (!wh) {
                result.errors.push(`第 ${lineNo} 行：仓库 [${whCode}] 不存在`);
                return;
            }
        }
        const qty = Number(quantity);
        if (quantity === undefined || quantity === '' || isNaN(qty)) {
            result.errors.push(`第 ${lineNo} 行：数量 [${quantity ?? ''}] 无效`);
            return;
        }
        if (qty < 0) {
            result.errors.push(`第 ${lineNo} 行：数量不能小于 0`);
            return;
        }
        const prc = price === undefined || price === '' ? (material.price || 0) : Number(price);
        if (isNaN(prc) || prc < 0) {
            result.errors.push(`第 ${lineNo} 行：单价 [${price ?? ''}] 无效`);
            return;
        }
        // FIX-OS-DATE-001: 行内日期优先，缺省用默认日期；非法日期告警并回落默认
        let rowDate = (dateRaw || '').trim();
        if (rowDate && !/^\d{4}-\d{2}-\d{2}$/.test(rowDate)) {
            result.errors.push(`第 ${lineNo} 行：日期 [${rowDate}] 格式应为 YYYY-MM-DD，已用默认日期`);
            rowDate = '';
        }
        result.items.push({
            material_id: material.id,
            warehouse_id: wh ? wh.id : '',
            quantity: qty,
            price: prc,
            remark: remark || '',
            date: rowDate || defaultDate || '',
        });
    });
    return result;
}

// BUG-2026-09-16-012：从粘贴文本收集候选物料编码（仅用于批量预热缓存）。
// 与 parsePasteLines 同一列序约定（编码在第 2 列 parts[1]、同样的表头跳过规则）——
// 两处列序必须一起改；完整行级校验仍在 parsePasteLines 内做，这里不做任何拦截。
function extractPasteCodes(text) {
    const codes = [];
    const rawLines = String(text || '').split(/\r?\n/).map(l => l.replace(/\r/g, '')).filter(l => l.trim() !== '');
    let startIndex = 0;
    if (rawLines.length) {
        const headFirst = splitCsvLine(rawLines[0])[0] || '';
        const headClean = headFirst.replace(/^"|"$/g, '').trim();
        if (headClean === '仓库' || headClean === '仓库编码' || headClean === '物料编码') {
            startIndex = 1;
        }
    }
    rawLines.slice(startIndex).forEach(line => {
        const code = splitCsvLine(line)[1];
        if (code) codes.push(code);
    });
    return codes;
}

let pasteLookupGeneration = 0;
let pasteLookupPending = false;
const PASTE_CONTEXT_FIELDS = ['pasteImportText', 'pasteDocDate', 'headerDocDate', 'headerWarehouse', 'headerRemark'];

function pasteLookupContext() {
    return PASTE_CONTEXT_FIELDS.map(id => document.getElementById(id)?.value || '');
}

function invalidatePasteLookup() {
    pasteLookupGeneration++;
    if (pasteLookupPending) {
        const feedback = document.getElementById('pasteImportFeedback');
        feedback.textContent = '录入内容已变更或解析已取消，请重新确认导入';
        feedback.className = 'form-text text-warning';
    }
    pasteLookupPending = false;
}

// 仅预热物料缓存，不保存库存。超过单次 500 编码时串行取全，任何失败均停止。
function ensurePasteMaterialsLoaded(codes, lookupUrl, isCurrent) {
    const seen = new Set();
    const pending = codes.map(code => String(code || '').trim()).filter(code => {
        const key = code.toLowerCase();
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return !findMaterialByCode(code);
    });
    function loadBatch(offset) {
        if (!isCurrent()) return Promise.resolve(false);
        if (offset >= pending.length) return Promise.resolve(true);
        return WMS.api.post(lookupUrl, { codes: pending.slice(offset, offset + 500) }).then(data => {
            if (!isCurrent()) return false;
            if (!data || !Array.isArray(data.items) || data.items.some(item =>
                !item || item.id == null || typeof item.code !== 'string')) {
                throw new Error('物料解析响应格式无效');
            }
            data.items.forEach(cacheMaterial);
            return loadBatch(offset + 500);
        });
    }
    return Promise.resolve().then(() => loadBatch(0));
}

// 粘贴导入：预热完成且用户上下文仍一致时才进入原保存流程。
function confirmPasteImport() {
    const generation = ++pasteLookupGeneration;
    pasteLookupPending = false;
    const text = document.getElementById('pasteImportText').value;
    const feedback = document.getElementById('pasteImportFeedback');
    if (!text.trim()) {
        feedback.textContent = '请先粘贴明细内容';
        feedback.className = 'form-text text-warning';
        return;
    }
    const context = pasteLookupContext();
    const isCurrent = () => generation === pasteLookupGeneration &&
        context.every((value, i) => value === pasteLookupContext()[i]);
    const lookupUrl = '/opening_stock/materials/lookup';
    pasteLookupPending = true;
    feedback.textContent = '正在解析物料编码…';
    feedback.className = 'form-text text-muted';
    return ensurePasteMaterialsLoaded(extractPasteCodes(text), lookupUrl, isCurrent)
        .then(ready => {
            if (!isCurrent()) {
                if (generation === pasteLookupGeneration) invalidatePasteLookup();
                return;
            }
            if (ready) {
                pasteLookupPending = false;
                doPasteImport(text, feedback, isCurrent);
            }
        }).catch(err => {
            if (!isCurrent()) {
                if (generation === pasteLookupGeneration) invalidatePasteLookup();
                return;
            }
            feedback.textContent = '物料解析失败：' + (err && err.message ? err.message : '未知错误');
            feedback.className = 'form-text text-danger';
        }).finally(() => {
            if (generation === pasteLookupGeneration) pasteLookupPending = false;
        });
}

async function doPasteImport(text, feedback, isCurrent) {
    const parsed = parsePasteLines(text, document.getElementById('pasteDocDate')?.value || '');
    if (!parsed.items.length) {
        feedback.textContent = '没有可导入的有效行。' + (parsed.errors[0] || '');
        feedback.className = 'form-text text-danger';
        return;
    }
    // 仓库回填：缺省时用表头仓库；缺表头且明细含多仓库/无仓库则拒绝（对齐 saveDocument 规则）
    const headerWarehouseId = document.getElementById('headerWarehouse')?.value;
    const items = parsed.items.slice();
    items.forEach(item => { if (!item.warehouse_id) item.warehouse_id = headerWarehouseId || ''; });
    if (items.some(item => !item.warehouse_id)) {
        feedback.textContent = '存在未指定仓库且表头未选仓库的行，请补选仓库';
        feedback.className = 'form-text text-warning';
        return;
    }
    const warn = parsed.errors.length ? `（另 ${parsed.errors.length} 行被跳过）` : '';
    // P1-D：这里**不**落草稿。粘贴导入不是"先并入网格再等用户保存"，
    // 它直接 POST /opening_stock/save 然后 700ms 跳转——网格里的 rows
    // 从头到尾没被粘贴内容碰过，此刻落草稿只会把用户原本那几行又存一遍
    // （存了也无意义，因为成功后立刻 clearDraft）。真正要做的是成功后清草稿。
    // ARCH-OS-DOC-01：粘贴的行要并入"当前这张单"。
    // 若还打 batch_save（不带 doc_id），后端会另建兼容单据，粘贴进来的行就跑
    // 到别的单里去了 —— 表现为"粘完保存，当前单没变化，还莫名多出一张单"。
    // 这里与 saveDocument 统一走 /opening_stock/save，并带上已有单据的 doc_id。
    const payload = { items };
    if (OPENING_DOC) payload.doc_id = OPENING_DOC.id;
    const headerDate = getHeaderDocDate();
    if (headerDate) payload.date = headerDate;
    if (headerWarehouseId) payload.warehouse_id = headerWarehouseId;
    const headerRemark = (document.getElementById('headerRemark')?.value || '').trim();
    if (headerRemark) payload.remark = headerRemark;
    if (OPENING_DOC || rows.some(row => row.material_id || row.material_code)) {
        if (!window.showConfirm) {
            feedback.textContent = '确认面板未就绪，请刷新页面后重试；尚未保存。';
            return;
        }
        const confirmed = await window.showConfirm(
            '粘贴导入会替换当前单据的全部明细。已建账的原明细将回冲库存，再按粘贴内容重新建账；未保存的明细也会被替换。确认继续？',
            {title:'替换期初单据明细', okText:'替换明细并保存', cancelText:'返回检查'});
        if (!confirmed) { feedback.textContent = '已取消，原明细未更改。'; return; }
        if (isCurrent && !isCurrent()) {
            feedback.textContent = '确认期间录入内容已变化，请重新导入。'; return;
        }
    }
    WMS.api.post('/opening_stock/save', payload)
        .then(data => {
            if (data && data.status === 'success') {
                // P1-D：粘贴导入同样直接落库，草稿使命结束 → 清掉。
                // 不清的话，导入成功后 700ms 跳转，详情页加载时残留草稿
                // 会把用户已经入库的行当成"未保存改动"再提示一遍。
                clearDraft();
                const modal = bootstrap.Modal.getInstance(document.getElementById('pasteImportModal'));
                if (modal) modal.hide();
                showToast((data.msg || '期初库存已导入') + warn, 'success');
                const newId = data.doc_id;
                setTimeout(() => {
                    if (newId) window.location.href = '/opening_stock/' + newId;
                    else window.location.reload();
                }, 700);
            } else {
                feedback.textContent = (data && data.msg) || '导入失败';
                feedback.className = 'form-text text-danger';
            }
        })
        .catch(err => {
            feedback.textContent = '导入失败：' + (err && err.message ? err.message : err);
            feedback.className = 'form-text text-danger';
        });
}

function pasteImport() {
    showPasteModal();
}

// BUG-2026-09-16-004 修复：导出 CSV 三处缺陷一并收口。
//   1) 原 `lines.join('\\n')` 在单引号字符串里是**字面反斜杠+n**，不是换行符——
//      整个文件塌成一行 `…备注"\\n"仓库"…`，Excel/WPS 打开只有第 1 行有内容。
//   2) 原表头行用裸 join(',')、未加引号，与数据行（全部带引号）格式不一致。
//   3) 原列序（仓库,编码,名称,规格,单位,数量,单价,余额,备注）与导入侧列序
//      （仓库,编码,数量,单价,备注,日期）**不一致**，导出的文件无法回导。
// 现改为与后端 /opening_stock/import/template 的官方列序完全一致
// （仓库编码,物料编码,物料名称,规格,单位,数量,单价,备注,日期），保证"导出→改→导入"闭环。
function csvCell(value) {
    return `"${String(value ?? '').replaceAll('"', '""')}"`;
}

function exportRows() {
    const exportRowsData = rows.filter(row => row.material_id);
    if (!exportRowsData.length) {
        showToast('当前单据没有可导出的明细行，请先添加明细', 'warning');
        return;
    }
    const headers = ['仓库编码', '物料编码', '物料名称', '规格', '单位', '数量', '单价', '备注', '日期'];
    // 日期取单据表头日期（真实 id 是 headerDocDate）；无单据时取粘贴导入的日期框兜底。
    const docDate = (document.getElementById('headerDocDate')?.value)
        || (OPENING_DOC && OPENING_DOC.date) || '';
    const lines = [headers.map(csvCell).join(',')];
    exportRowsData.forEach(row => {
        lines.push([
            warehouseCodeById[row.warehouse_id] || row.warehouse_name || '',
            row.material_code,
            row.material_name,
            row.spec,
            row.unit,
            row.quantity,
            row.price,
            row.remark,
            docDate,
        ].map(csvCell).join(','));
    });
    // 真实换行用 '\n'（不能写成 '\\n'）；前置 BOM 让 Excel 正确识别 UTF-8 中文。
    const blob = new Blob(['\ufeff' + lines.join('\n')], {type: 'text/csv;charset=utf-8;'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'opening_stock_' + ((OPENING_DOC && OPENING_DOC.doc_no) || 'new') + '.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    showToast(`已导出 ${exportRowsData.length} 行明细`, 'success');
}

function updateTotal() {
    if (typeof WMS !== 'undefined' && WMS.refreshQuantityTotals) WMS.refreshQuantityTotals('openingGrid');
    const total = rows.reduce((sum, row) => sum + amountOf(row), 0);
    document.getElementById('totalAmount').textContent = formatMoney(total, true);
}

function formatMoney(value, symbol = true) {
    const number = Number(value || 0).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    return symbol ? `¥${number}` : number;
}



function switchTab(tabName) {
    const detailView = document.getElementById('detailView');
    const summaryView = document.getElementById('summaryView');
    const tabs = document.querySelectorAll('.tabs .tab');
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
    if (tabName === 'summary') {
        detailView.style.display = 'none';
        summaryView.style.display = '';
        renderSummary();
    } else {
        detailView.style.display = '';
        summaryView.style.display = 'none';
    }
}

function renderSummary() {
    const summaryBody = document.getElementById('summaryGridBody');
    const grouped = {};
    rows.forEach(row => {
        if (!row.material_id) return;
        const key = (row.warehouse_id || '') + '|' + row.material_id;
        if (!grouped[key]) {
            grouped[key] = {
                warehouse_id: row.warehouse_id,
                warehouse_name: row.warehouse_name || '',
                material_id: row.material_id,
                material_code: row.material_code || '',
                material_name: row.material_name || '',
                spec: row.spec || '',
                unit: row.unit || '',
                total_qty: 0,
                total_amount: 0
            };
        }
        const g = grouped[key];
        const qty = Number(row.quantity || 0);
        g.total_qty += qty;
        g.total_amount += qty * Number(row.price || 0);
    });
    const items = Object.values(grouped);
    if (!items.length) {
        summaryBody.innerHTML = '<tr><td colspan="9" class="text-center text-muted" style="padding:18px;">暂无数据，请先在明细中录入物料</td></tr>';
        return;
    }
    summaryBody.innerHTML = items.map((g, i) => {
        const avgPrice = g.total_qty > 0 ? g.total_amount / g.total_qty : 0;
        return `<tr>
            <td class="row-no">${i + 1}</td>
            <td>${escapeHtml(g.warehouse_name)}</td>
            <td>${escapeHtml(g.material_code)}</td>
            <td>${escapeHtml(g.material_name)}</td>
            <td>${escapeHtml(g.spec)}</td>
            <td>${escapeHtml(g.unit)}</td>
            <td class="num">${formatMoney(g.total_qty, false)}</td>
            <td class="num">${formatMoney(avgPrice, false)}</td>
            <td class="amount">${formatMoney(g.total_amount, true)}</td>
        </tr>`;
    }).join('');
}

document.addEventListener('click', event => {
    if (!event.target.closest('#materialMenu') && !event.target.closest('.code-cell')) {
        closeMaterialMenu();
    }
});

document.addEventListener('DOMContentLoaded', function() {
    PASTE_CONTEXT_FIELDS.forEach(function(id) {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('input', invalidatePasteLookup);
        el.addEventListener('change', invalidatePasteLookup);
    });
    const pasteModal = document.getElementById('pasteImportModal');
    if (pasteModal) pasteModal.addEventListener('hide.bs.modal', invalidatePasteLookup);
    // 首次渲染前先把勾选态对齐到已有行数，否则编辑已有单据时
    // selectedFlags 为空数组、syncCheckAllState 读到 undefined 会误判全选态
    syncSelectedFlags(rows.length);
    renderRows();
    // P1-D：渲染完再看有没有可恢复的草稿（此时才拿得到"当前是否已有内容"）
    checkDraftOnLoad();
    // P1-D：表头三件套（日期/仓库/备注）也是用户录入的一部分——
    // 用户选好日期仓库、录了十几行，刷新后表头蒸发同样得重来。
    // 它们不在 rows 里，用委托监听统一记录（草稿里一并存 head 字段）。
    ['headerDocDate', 'headerWarehouse', 'headerRemark'].forEach(function(id) {
        const el = document.getElementById(id);
        if (!el) return;
        const evt = el.tagName === 'SELECT' ? 'change' : 'input';
        el.addEventListener(evt, function() { scheduleDraftSave(); });
    });
});

// P1-D：关页/刷新前把待写草稿立刻落盘。
// 键入是防抖 400ms 的，用户敲完最后一个数立刻刷新的场景下定时器还没触发，
// 这时只能靠 beforeunload/pagehide 补一刀——否则"防丢"在最后一步最该丢。
window.addEventListener('beforeunload', function() {
    if (draftSaveTimer) {
        clearTimeout(draftSaveTimer);
        draftSaveTimer = null;
        persistDraftNow();
    }
});
// pagehide 兜移动端：iOS Safari 等场景 beforeunload 不一定触发
window.addEventListener('pagehide', function() {
    if (draftSaveTimer) {
        clearTimeout(draftSaveTimer);
        draftSaveTimer = null;
        persistDraftNow();
    }
});
