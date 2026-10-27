/* Shared read-only toolbar for server-rendered sales and stock reports. */
(function () {
    'use strict';
    function initialize(root) {
        if (root.dataset.reportReady) return;
        root.dataset.reportReady = '1';
        var kind = root.dataset.reportKind;
        var scope = root.querySelector('[data-report-scope]');
        var select = root.querySelector('[data-report-template]');
        var preview = root.querySelector('[data-report-preview]');
        var download = root.querySelector('[data-report-download]');
        var status = root.querySelector('[data-report-status]');
        var retry = root.querySelector('[data-report-retry]');
        var manage = root.querySelector('[data-report-manage]');
        var form = document.querySelector('form[method="get"]');
        var requestId = 0, ready = false, available = new Set();
        var initialForm = formValues();
        var applied = new URLSearchParams(window.location.search);
        initialForm.forEach(function (value, key) { if (value) applied.set(key, value); else applied.delete(key); });
        if (!applied.get('warehouse_id') && root.dataset.warehouse) applied.set('warehouse_id', root.dataset.warehouse);
        ['csrf_token', 'page', 'per_page', 'page_size', 'embedded', 'export', 'template_id'].forEach(function (key) { applied.delete(key); });

        function formValues() {
            var result = new URLSearchParams();
            if (form) new FormData(form).forEach(function (value, key) {
                if (key !== 'csrf_token' && key !== 'embedded') result.set(key, String(value).trim());
            });
            result.sort();
            return result;
        }
        function targetCode() {
            if (kind === 'stock') return 'stock_query';
            if (kind === 'summary') return 'report_sales_summary_' + scope.value;
            return 'report_sales_' + kind;
        }
        function allowOutput() {
            var warehouse = applied.get('warehouse_id');
            return !!warehouse && warehouse !== '0';
        }
        function enableOutputs(enabled) {
            preview.disabled = !enabled;
            download.classList.toggle('disabled', !enabled);
            download.setAttribute('aria-disabled', String(!enabled));
            download.tabIndex = enabled ? 0 : -1;
        }
        function currentFilters() {
            if (formValues().toString() !== initialForm.toString()) {
                status.textContent = '筛选条件已修改，请先点击查询或筛选，再输出报表。';
                return false;
            }
            if (!allowOutput()) {
                status.textContent = '请选择具体仓库并查询后再输出报表。';
                return false;
            }
            return true;
        }
        async function loadTemplates() {
            var token = ++requestId;
            ready = false;
            available = new Set();
            enableOutputs(false);
            select.disabled = true;
            retry.hidden = true;
            status.textContent = '正在加载模板…';
            if (manage) manage.href = '/print_templates?target_type=report&target_code=' + encodeURIComponent(targetCode());
            try {
                var result = await window.WMS.api.get('/doc_print_templates/' + encodeURIComponent(targetCode()) + '.json');
                if (token !== requestId) return;
                if (!result || result.status !== 'success' || !Array.isArray(result.templates)) throw new Error('打印模板加载失败');
                var usable = result.templates.filter(function (item) { return item.has_file !== false; });
                select.innerHTML = '';
                if (!usable.length) {
                    var builtin = document.createElement('option');
                    builtin.value = '';
                    builtin.textContent = '系统内置模板';
                    select.appendChild(builtin);
                    available.add('');
                }
                result.templates.forEach(function (item) {
                    var option = document.createElement('option');
                    option.value = String(item.id);
                    option.textContent = item.name + (item.has_file === false ? '（文件缺失）' : item.is_default ? '（默认）' : '');
                    option.disabled = item.has_file === false;
                    select.appendChild(option);
                    if (!option.disabled) available.add(option.value);
                });
                var chosen = usable.find(function (item) { return item.is_default; }) || usable[0];
                select.value = chosen ? String(chosen.id) : '';
                select.disabled = false;
                ready = true;
                download.href = outputUrl('download');
                enableOutputs(allowOutput());
                status.textContent = allowOutput() ? '输出当前已查询条件的全部结果；模板文件为 Excel。' : '请选择具体仓库并查询后再打印。';
            } catch (error) {
                if (token !== requestId) return;
                status.textContent = (error.message || '打印模板加载失败') + '，请重新加载。';
                retry.hidden = false;
            }
        }
        function outputUrl(mode) {
            var params = new URLSearchParams(applied.toString());
            if (scope) params.set('scope', scope.value);
            if (select.value) params.set('template_id', select.value);
            if (kind === 'stock' && mode === 'download') params.set('template_mode', '1');
            var path = kind === 'stock' ? '/report/stock/' + (mode === 'preview' ? 'print_preview' : 'print')
                : '/sales/' + encodeURIComponent(kind) + '/' + (mode === 'preview' ? 'print_preview' : 'print_excel');
            return path + '?' + params.toString();
        }
        function output(mode) {
            if (!ready || !currentFilters()) return;
            if (!available.has(select.value)) { status.textContent = '所选模板不可用，请重新选择或重新加载。'; return; }
            window.open(outputUrl(mode), '_blank', 'noopener');
        }
        root.querySelector('#refreshReportBtn').addEventListener('click', function () { window.location.reload(); });
        root.querySelector('#exportReportBtn').addEventListener('click', function () {
            if (!currentFilters()) return;
            var action = window[root.dataset.exportAction];
            if (typeof action === 'function') action();
            else if (root.dataset.exportUrl) {
                var target = new URL(root.dataset.exportUrl, window.location.origin);
                applied.forEach(function (value, key) { target.searchParams.set(key, value); });
                window.location.assign(target.pathname + target.search);
            }
        });
        preview.addEventListener('click', function () { output('preview'); });
        download.addEventListener('click', function (event) { event.preventDefault(); output('download'); });
        retry.addEventListener('click', loadTemplates);
        if (kind !== 'stock') select.addEventListener('change', function () {
            if (ready && available.has(select.value)) download.href = outputUrl('download');
        });
        if (scope) scope.addEventListener('change', loadTemplates);
        root.querySelectorAll('[data-report-fields]').forEach(function (button) {
            var table = document.getElementById(button.dataset.reportFields);
            var localButton = table && table.closest('.card').querySelector('button');
            button.disabled = !localButton;
            if (localButton) button.addEventListener('click', function () { localButton.click(); });
        });
        root.querySelector('#reportPrintMenu').addEventListener('keydown', function (event) {
            if (event.key === 'Escape') { event.currentTarget.open = false; event.currentTarget.querySelector('summary').focus(); }
        });
        loadTemplates();
    }
    function start() { document.querySelectorAll('[data-report-workbench]').forEach(initialize); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
})();
