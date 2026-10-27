/**
 * Excel导入导出组件
 * 支持单据明细的批量导入和导出
 */

class ExcelImportExport {
    static loadXlsx() {
        if (window.XLSX) return Promise.resolve(window.XLSX);
        if (!ExcelImportExport.xlsxPromise) {
            const script = document.createElement('script');
            script.src = ExcelImportExport.xlsxUrl;
            ExcelImportExport.xlsxPromise = new Promise((resolve, reject) => {
                script.onload = () => {
                    if (window.XLSX) resolve(window.XLSX);
                    else reject(new Error('Excel组件未正确初始化，请重试'));
                };
                script.onerror = () => reject(new Error('Excel组件加载失败，请检查网络后重试'));
                document.head.appendChild(script);
            }).catch(error => {
                script.remove();
                ExcelImportExport.xlsxPromise = null;
                throw error;
            });
        }
        return ExcelImportExport.xlsxPromise;
    }

    constructor(options = {}) {
        this.fileRevision = 0;
        this.importPending = false;
        this.importCommitted = false;
        this.options = {
            tableId: options.tableId || 'itemTable',
            exportUrl: options.exportUrl || null,
            importUrl: options.importUrl || null,
            templateUrl: options.templateUrl || null,
            fileName: options.fileName || '单据明细',
            columns: options.columns || [],
            onImportSuccess: options.onImportSuccess || null,
            onImportError: options.onImportError || null
        };

        this.init();
    }

    init() {
        // 创建导入导出按钮
        this.createButtons();
        // 创建导入模态框
        this.createImportModal();
    }

    createButtons() {
        // 查找表格容器内的工具栏（更精确的定位）
        const tableContainer = document.querySelector('.order-table-container');
        if (!tableContainer) {
            console.error('ExcelImportExport: 找不到 .order-table-container');
            return;
        }

        let toolbar = tableContainer.querySelector('.order-toolbar');

        // 如果没有 order-toolbar，尝试查找 table-header-custom
        if (!toolbar) {
            const header = tableContainer.querySelector('.table-header-custom');
            if (header && header.parentElement) {
                // 如果父元素不是 order-toolbar，创建一个
                if (!header.parentElement.classList.contains('order-toolbar')) {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'order-toolbar';
                    header.parentElement.insertBefore(wrapper, header);
                    wrapper.appendChild(header);
                    toolbar = wrapper;
                } else {
                    toolbar = header.parentElement;
                }
            }
        }

        if (!toolbar) {
            console.error('ExcelImportExport: 找不到工具栏容器');
            return;
        }

        // 查找或创建按钮组
        let btnGroup = toolbar.querySelector('.btn-group');
        if (!btnGroup) {
            btnGroup = document.createElement('div');
            btnGroup.className = 'btn-group';
            toolbar.appendChild(btnGroup);
        }

        // 导出按钮
        const exportBtn = document.createElement('button');
        exportBtn.className = 'btn-order btn-order-success btn-order-sm';
        exportBtn.innerHTML = '<i class="bi bi-file-earmark-excel"></i> 导出Excel';
        exportBtn.onclick = () => this.exportToExcel();
        btnGroup.appendChild(exportBtn);

        // 导入按钮
        const importBtn = document.createElement('button');
        importBtn.className = 'btn-order btn-order-primary btn-order-sm';
        importBtn.innerHTML = '<i class="bi bi-upload"></i> 导入Excel';
        importBtn.onclick = () => this.showImportModal();
        btnGroup.appendChild(importBtn);

        // 下载模板按钮
        if (this.options.templateUrl) {
            const templateBtn = document.createElement('button');
            templateBtn.className = 'btn-order btn-order-secondary btn-order-sm';
            templateBtn.innerHTML = '<i class="bi bi-download"></i> 下载模板';
            templateBtn.onclick = () => this.downloadTemplate();
            btnGroup.appendChild(templateBtn);
        }
    }

    createImportModal() {
        if (document.getElementById('excelImportModal')) {
            return;
        }

        const modalHtml = `
        <div class="modal fade" id="excelImportModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5><i class="bi bi-upload"></i> 导入Excel</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-info d-flex align-items-start">
                            <i class="bi bi-info-circle me-2 mt-1"></i>
                            <div>
                                <strong>导入说明：</strong>
                                <ul class="mb-0 mt-2">
                                    <li>支持 .xlsx 和 .xls 格式</li>
                                    <li>第一行为表头，从第二行开始为数据</li>
                                    <li>必填列：<span id="excelRequiredColumns"></span></li>
                                    <li>建议先下载模板，按模板格式填写数据</li>
                                </ul>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-medium">选择Excel文件</label>
                            <input type="file" class="form-control" id="excelFileInput"
                                   accept=".xlsx,.xls" />
                        </div>
                        <div id="importPreview" class="d-none">
                            <label class="form-label fw-medium">数据预览</label>
                            <div class="table-responsive" style="max-height: 300px;">
                                <table class="table table-sm table-bordered" id="previewTable">
                                    <thead></thead>
                                    <tbody></tbody>
                                </table>
                            </div>
                            <div class="mt-2">
                                <span class="badge bg-primary" id="previewCount">0</span> 条数据待导入
                            </div>
                        </div>
                        <div id="excelImportResult" class="d-none" role="status" style="white-space: pre-wrap;"></div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button class="btn btn-primary" id="confirmImportBtn" disabled>
                            <i class="bi bi-check"></i> 确认导入
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        document.getElementById('excelRequiredColumns').textContent = this.getRequiredColumns();

        // 绑定文件选择事件
        document.getElementById('excelFileInput').addEventListener('change', (e) => {
            this.handleFileSelect(e);
        });

        // 绑定确认导入事件
        document.getElementById('confirmImportBtn').addEventListener('click', () => {
            this.confirmImport();
        });
        document.getElementById('excelImportModal').addEventListener('hide.bs.modal', () => {
            this.resetFileSelection();
        });
    }

    getRequiredColumns() {
        const required = this.options.columns.filter(col => col.required);
        return required.map(col => col.label).join('、') || '物料编码、数量';
    }

    showImportModal() {
        this.resetFileSelection();
        const modal = new bootstrap.Modal(document.getElementById('excelImportModal'));
        modal.show();
    }

    resetFileSelection(clearInput = true) {
        this.fileRevision++;
        this.selectedFile = null;
        this.previewData = null;
        const input = document.getElementById('excelFileInput');
        if (input && clearInput) input.value = '';
        const preview = document.getElementById('importPreview');
        if (preview) preview.classList.add('d-none');
        const btn = document.getElementById('confirmImportBtn');
        if (btn) btn.disabled = true;
    }

    showImportResult(message, type = 'danger') {
        const result = document.getElementById('excelImportResult');
        if (!result) return;
        result.textContent = message;
        result.className = message ? 'alert alert-' + type + ' mt-3' : 'd-none';
    }

    async handleFileSelect(event) {
        if (this.importPending) return;
        const file = event.target.files[0];
        this.resetFileSelection(false);
        this.importCommitted = false;
        this.showImportResult('');
        if (!file) return;

        // 保存原始文件对象，供 confirmImport 上传给后端（后端接口接收文件而非 JSON）
        this.selectedFile = file;
        const revision = this.fileRevision;
        const isCurrent = () => this.fileRevision === revision && this.selectedFile === file;
        let xlsx;
        try {
            xlsx = await ExcelImportExport.loadXlsx();
        } catch (error) {
            if (isCurrent()) this.showToast(error.message, 'danger');
            return;
        }
        if (!isCurrent()) return;

        // 使用SheetJS读取Excel
        const reader = new FileReader();
        reader.onload = (e) => {
            if (!isCurrent()) return;
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = xlsx.read(data, { type: 'array' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                const jsonData = xlsx.utils.sheet_to_json(firstSheet);

                if (jsonData.length === 0) {
                    this.showToast('Excel文件为空', 'warning');
                    return;
                }

                this.previewData = jsonData;
                this.showPreview(jsonData);
                document.getElementById('confirmImportBtn').disabled = false;
            } catch (error) {
                this.showToast('读取Excel文件失败：' + error.message, 'danger');
            }
        };
        reader.onerror = () => {
            if (isCurrent()) this.showToast('读取Excel文件失败，请重新选择文件', 'danger');
        };
        try {
            reader.readAsArrayBuffer(file);
        } catch (error) {
            if (isCurrent()) this.showToast('读取Excel文件失败：' + error.message, 'danger');
        }
    }

    showPreview(data) {
        const preview = document.getElementById('importPreview');
        const table = document.getElementById('previewTable');
        const thead = table.querySelector('thead');
        const tbody = table.querySelector('tbody');

        // 清空
        thead.innerHTML = '';
        tbody.innerHTML = '';

        if (data.length === 0) return;

        // 表头
        const headers = Object.keys(data[0]);
        const headerRow = document.createElement('tr');
        headers.forEach(header => {
            const th = document.createElement('th');
            th.textContent = header;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);

        // 数据（最多显示10行）
        const displayData = data.slice(0, 10);
        displayData.forEach(row => {
            const tr = document.createElement('tr');
            headers.forEach(header => {
                const td = document.createElement('td');
                td.textContent = row[header] == null ? '' : row[header];
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

        document.getElementById('previewCount').textContent = data.length;
        preview.classList.remove('d-none');
    }

    async confirmImport() {
        if (this.importPending || this.importCommitted) return;
        if (!this.previewData || this.previewData.length === 0) {
            this.showToast('没有可导入的数据', 'warning');
            return;
        }

        if (!this.options.importUrl) {
            this.showToast('未配置导入接口', 'danger');
            return;
        }

        // 后端导入接口接收文件上传（request.files.get('file')），因此用 FormData 上传原始 Excel 文件，
        // 不能用 application/json 提交预览数据（否则后端拿不到 file 会报"请选择要导入的文件"）
        if (!this.selectedFile) {
            this.showToast('未找到要导入的文件，请重新选择', 'danger');
            return;
        }

        const file = this.selectedFile;
        const rowCount = this.previewData.length;
        const btn = document.getElementById('confirmImportBtn');
        const input = document.getElementById('excelFileInput');
        const originalButton = { disabled: btn.disabled, html: btn.innerHTML };
        const originalInputDisabled = input && input.disabled;
        let failureResponse = null;
        let committedResult = '';
        let navigationPending = false;
        try {
            const formData = new FormData();
            formData.append('file', file);
            this.importPending = true;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> 导入中...';
            if (input) input.disabled = true;
            this.showImportResult('正在导入 ' + file.name + '，请等待结果。', 'info');
            const res = await WMS.api.postRaw(this.options.importUrl, formData);
            if (!res || res.status !== 'success') {
                failureResponse = res;
                throw new Error(res && res.msg ? res.msg : '导入接口未返回成功结果，请先核对单据再决定是否重试');
            }
            // 服务端已确认写入。后续提示、回调或导航出错不得再次开放同一份文件提交。
            this.importCommitted = true;
            let message = res.msg || `成功导入 ${res.count == null ? rowCount : res.count} 条数据`;
            if (res.msg && res.count != null && Number(res.count) === 0) {
                message += '\n本次成功导入：0 条。';
            }
            const warnings = Array.isArray(res.warnings) ? res.warnings.join('\n') : String(res.warnings || '');
            const review = (res.count != null && Number(res.count) === 0) || !!warnings;
            committedResult = message + (warnings ? '\n' + warnings : '');
            this.showImportResult(committedResult, review ? 'warning' : 'success');
            this.showToast(message, review ? 'warning' : 'success');
            if (!review) {
                bootstrap.Modal.getInstance(document.getElementById('excelImportModal')).hide();
            }
            if (this.options.onImportSuccess) {
                await this.options.onImportSuccess(res);
            } else if (!review) {
                navigationPending = true;
                setTimeout(() => location.reload(), 800);
            }
        } catch (error) {
            if (this.importCommitted) {
                const message = '导入已成功，后续页面处理失败。请核对结果后刷新页面，勿重复导入。';
                this.showImportResult(committedResult + '\n' + message, 'warning');
                this.showToast(message, 'warning');
            } else {
                const message = '导入失败：' + (error.message || '请核对单据后重试');
                this.showImportResult(message, 'danger');
                this.showToast(message, 'danger');
                if (failureResponse && this.options.onImportError) {
                    try {
                        await this.options.onImportError(failureResponse);
                    } catch (callbackError) {
                        this.showImportResult(message + '\n错误提示处理失败，请核对单据后重试。', 'danger');
                    }
                }
            }
        } finally {
            this.importPending = navigationPending;
            if (input && !navigationPending) input.disabled = originalInputDisabled;
            btn.disabled = this.importCommitted || originalButton.disabled || !this.selectedFile || !this.previewData;
            btn.innerHTML = this.importCommitted ? '<i class="bi bi-check"></i> 已处理，请核对结果' : originalButton.html;
        }
    }

    exportToExcel() {
        if (this.options.exportUrl) {
            // 使用服务器端导出
            window.open(this.options.exportUrl, '_blank');
        } else {
            // 使用客户端导出
            return this.clientExport();
        }
    }

    async clientExport() {
        const table = document.getElementById(this.options.tableId);
        if (!table) {
            this.showToast('未找到表格', 'warning');
            return;
        }

        // 获取表格数据
        const data = [];
        const exportColumns = [];

        // 表头
        const headerCells = table.querySelectorAll('thead th');
        headerCells.forEach((th, index) => {
            const text = th.textContent.trim();
            if (text && text !== '序' && text !== '操作' && !th.querySelector('input[type="checkbox"]')) {
                exportColumns.push({ index: index, header: text });
            }
        });

        // 数据行
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(tr => {
            if (tr.querySelector('.empty-state')) return;

            const rowData = {};
            const cells = tr.querySelectorAll('td');
            exportColumns.forEach(column => {
                const td = cells[column.index];
                if (td && !td.querySelector('input[type="checkbox"]') && !td.querySelector('.btn')) {
                    let value = td.textContent.trim();
                    // 移除货币符号
                    value = value.replace(/¥|￥/g, '');
                    rowData[column.header] = value;
                }
            });

            if (Object.keys(rowData).length > 0) {
                data.push(rowData);
            }
        });

        if (data.length === 0) {
            this.showToast('没有可导出的数据', 'warning');
            return;
        }

        try {
            const xlsx = await ExcelImportExport.loadXlsx();
            const ws = xlsx.utils.json_to_sheet(data);
            const wb = xlsx.utils.book_new();
            xlsx.utils.book_append_sheet(wb, ws, '明细');

            // 下载
            const fileName = `${this.options.fileName}_${this.formatDate(new Date())}.xlsx`;
            xlsx.writeFile(wb, fileName);

            this.showToast('导出成功', 'success');
        } catch (error) {
            this.showToast('导出失败：' + error.message, 'danger');
        }
    }

    downloadTemplate() {
        if (this.options.templateUrl) {
            window.open(this.options.templateUrl, '_blank');
        } else {
            // 生成模板
            return this.generateTemplate();
        }
    }

    async generateTemplate() {
        const headers = this.options.columns.map(col => col.label);
        const example = {};
        this.options.columns.forEach(col => {
            example[col.label] = col.example || '';
        });

        try {
            const xlsx = await ExcelImportExport.loadXlsx();
            const ws = xlsx.utils.json_to_sheet([example]);
            const wb = xlsx.utils.book_new();
            xlsx.utils.book_append_sheet(wb, ws, '模板');
            xlsx.writeFile(wb, `${this.options.fileName}_导入模板.xlsx`);
            this.showToast('模板下载成功', 'success');
        } catch (error) {
            this.showToast('模板下载失败：' + error.message, 'danger');
        }
    }

    formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hour = String(date.getHours()).padStart(2, '0');
        const minute = String(date.getMinutes()).padStart(2, '0');
        return `${year}${month}${day}_${hour}${minute}`;
    }

    showToast(message, type = 'info') {
        if (typeof showToast === 'function') {
            showToast(message, type);
        } else {
            alert(message); // allow-alert: showToast 全局函数尚未加载时的终极 fallback
        }
    }
}

// 导出到全局
const excelComponentUrl = new URL(document.currentScript.src, document.baseURI);
const excelLibraryUrl = new URL('xlsx.full.min.js', excelComponentUrl);
excelLibraryUrl.search = excelComponentUrl.search;
ExcelImportExport.xlsxUrl = excelLibraryUrl.href;
window.ExcelImportExport = ExcelImportExport;
