// Page code for the migrated in_order list.
document.addEventListener('DOMContentLoaded', function() {
    var configNode = document.getElementById('inOrderListConfig');
    var pageConfig = configNode ? JSON.parse(configNode.textContent) : {};
    initCheckAll('inOrderTable');
    setupResizableTable({
        tableSelector: '.table-responsive-wrapper table',
        tableId: 'in-order-detail-list',
        minWidth: 70
    });

    document.querySelectorAll('.sortable-header').forEach(function(th) {
        th.addEventListener('click', function() {
            var sortField = this.dataset.sortable;
            if (!sortField) return;
            var currentSort = pageConfig.sortBy || 'id';
            var currentOrder = pageConfig.sortOrder || 'desc';
            var newOrder = (currentSort === sortField && currentOrder === 'asc') ? 'desc' : 'asc';
            var url = new URL(window.location.href);
            url.searchParams.set('sort', sortField);
            url.searchParams.set('order', newOrder);
            url.searchParams.set('page', '1');
            window.location.href = url.toString();
        });
    });

    // 供应商筛选：手工输入时清空已选 id，让后端走 supplier_name 模糊匹配；
    // quick-select 点选后只派发 change 事件回填 id（不触发 input），不会被误清。
    (function() {
        var sfInput = document.getElementById('supplierFilterInput');
        var sfHidden = document.getElementById('supplierFilterId');
        if (sfInput && sfHidden) {
            sfInput.addEventListener('input', function() { sfHidden.value = ''; });
        }
    })();

    // 工程名称快速匹配（BUG-2026-08-29-004）：输入关键词弹出合同档案中的候选工程，
    // 上下键/回车选择回填完整工程名；数据源 /api/contracts（工程名称+合同编号模糊）。
    (function() {
        var input = document.getElementById('projectNameFilterInput');
        var dropdown = document.getElementById('projectNameDropdown');
        if (!input || !dropdown) return;
        var activeDropdown = null;
        var timer = null;
        var cache = Object.create(null);
        var queryVersion = 0;
        var queryActive = false;



        function hideDropdown() {
            clearTimeout(timer);
            queryVersion++;
            queryActive = false;
            dropdown.style.display = 'none';
            activeDropdown = null;
        }

        function showDropdown() {
            WMS.positionDropdown(input, dropdown, {maxHeight: 220});
            dropdown.style.display = 'block';
            activeDropdown = dropdown;
        }

        function render(list) {
            if (!list.length) {
                dropdown.innerHTML = '<div style="padding:6px 10px;color:#999;">无匹配工程</div>';
            } else {
                dropdown.innerHTML = list.map(function(c, idx) {
                    return '<div class="pf-item' + (idx === 0 ? ' active' : '') + '" data-pn="' + escapeHtml(c.project_name || '') + '" style="padding:6px 10px;cursor:pointer;border-bottom:1px solid #f0f0f0;">'
                        + '<span>' + escapeHtml(c.project_name || '') + '</span>'
                        + (c.contract_no ? ' <span style="color:#999;font-size:12px;">' + escapeHtml(c.contract_no) + '</span>' : '')
                        + '</div>';
                }).join('');
                var items = dropdown.querySelectorAll('.pf-item[data-pn]');
                for (var k = 0; k < items.length; k++) {
                    items[k].addEventListener('mousedown', function(ev) {
                        ev.preventDefault();
                        input.value = this.getAttribute('data-pn');
                        hideDropdown();
                    });
                }
            }
            showDropdown();
        }

        function isCurrent(kw, version) {
            return queryActive && version === queryVersion && input.isConnected !== false && input.value.trim() === kw;
        }

        function query(kw, version) {
            if (!isCurrent(kw, version)) return;
            if (cache[kw]) { render(cache[kw]); return; }
            dropdown.innerHTML = '<div style="padding:6px 10px;color:#999;">加载中...</div>';
            showDropdown();
            WMS.api.getRaw('/api/contracts?keyword=' + encodeURIComponent(kw)).then(function(j) {
                if (!isCurrent(kw, version)) return;
                if (!(j && j.status === 'success' && j.data && Array.isArray(j.data.contracts) &&
                    j.data.contracts.every(function(c) { return c && typeof c === 'object'; }))) {
                    throw new Error('工程查询返回格式异常');
                }
                var list = j.data.contracts;
                cache[kw] = list;
                render(list);
            }).catch(function() {
                if (isCurrent(kw, version)) {
                    dropdown.innerHTML = '<div style="padding:6px 10px;color:#999;">加载失败</div>';
                    showDropdown();
                }
            });
        }

        function search(delayed) {
            hideDropdown();
            var kw = input.value.trim();
            if (!kw) return;
            queryActive = true;
            var version = queryVersion;
            if (cache[kw]) { render(cache[kw]); return; }
            if (delayed) timer = setTimeout(function() { query(kw, version); }, 200);
            else query(kw, version);
        }

        input.addEventListener('input', function() { search(true); });
        input.addEventListener('focus', function() {
            search(false);
        });
        input.addEventListener('blur', hideDropdown);
        document.addEventListener('click', function(ev) {
            if (ev.target !== input && !dropdown.contains(ev.target)) hideDropdown();
        });
        input.addEventListener('keydown', function(ev) {
            if (ev.key === 'Escape') { hideDropdown(); return; }
            if (!activeDropdown) return;
            if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
                ev.preventDefault();
                var items = Array.from(dropdown.querySelectorAll('.pf-item[data-pn]'));
                if (!items.length) return;
                var cur = Math.max(0, items.findIndex(function(it) { return it.classList.contains('active'); }));
                var next = (cur + (ev.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
                items[cur].classList.remove('active');
                items[next].classList.add('active');
                items[next].scrollIntoView({ block: 'nearest' });
                return;
            }
            if (ev.key === 'Enter') {
                var sel = dropdown.querySelector('.pf-item.active');
                if (sel) {
                    ev.preventDefault();
                    input.value = sel.getAttribute('data-pn');
                    hideDropdown();
                }
            }
        });
    })();

});

// 快速搜索入库单
function changePerPage(perPage) {
    var url = new URL(window.location.href);
    url.searchParams.set('per_page', perPage);
    url.searchParams.set('page', '1');
    window.location.href = url.toString();
}

function selectedOrderIds(tableId) {
    var ids = [];
    document.querySelectorAll('#' + tableId + ' .check-item:checked').forEach(function(cb) {
        if (ids.indexOf(cb.value) === -1) ids.push(cb.value);
    });
    return ids;
}

function batchInOrderAction(url, emptyMessage, confirmMessage) {
    var ids = selectedOrderIds('inOrderTable');
    if (!ids.length) {
        showToast(emptyMessage, 'warning');
        return;
    }
    const isPrint = url === '/in_order/batch_print';
    if (isPrint && ids.length !== 1) {
        showToast('打印已选暂限1张，请只选择一张入库单；多单合并打印暂未支持', 'warning', 5000);
        return;
    }
    if (ids.length > 100) {
        showToast('单次批量操作不能超过 100 条，请分批处理', 'warning', 5000);
        return;
    }
    showConfirm(confirmMessage, {title: '批量处理入库单'}).then(function(confirmed) {
        if (!confirmed) return;
        if (url === '/in_order/batch_export') {
            WMS.api.postResponse(url, {ids: ids})
            .then(function(response) {
                const contentType = (response.headers.get('Content-Type') || '').toLowerCase();
                if (!contentType.includes('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') &&
                        !contentType.includes('application/octet-stream')) {
                    return response.json().catch(function() { return {}; }).then(function(data) {
                        throw new Error((data && data.msg) || '导出失败：服务器未返回Excel文件');
                    });
                }
                const filename = filenameFromDisposition(response.headers.get('Content-Disposition'), '入库单批量导出.xlsx');
                return response.blob().then(function(blob) {
                    downloadBlob(blob, filename, contentType);
                    showToast('导出成功', 'success');
                });
            })
            .catch(function(error) { showToast('导出失败：' + error.message, 'danger', 5000); });
            return;
        }
        WMS.api.postRaw(url, {ids: ids})
        .then(function(data) {
            if (data.status === 'success') {
                if (isPrint) {
                    if (data.redirect) window.location.href = data.redirect.replace(/\/print$/, '/print_options');
                    else showToast('打印失败：服务器未返回打印地址', 'danger', 5000);
                    return;
                }
                showToast(data.msg || '操作成功', 'success');
                setTimeout(function(){ location.reload(); }, 650);
            } else {
                showToast(data.msg || '操作失败', 'danger', 5000);
            }
        })
        .catch(function(error) { showToast('操作失败：' + error.message, 'danger', 5000); });
    });
}

async function submitDocumentImport(formId, fileId) {
    if (submitDocumentImport.pending) return;
    const form = document.getElementById(formId);
    const fileInput = document.getElementById(fileId);
    if (!form || !fileInput || !fileInput.files.length) return;
    const selectedFile = fileInput.files[0];
    const button = document.getElementById('inOrderImportFileButton');
    const wasDisabled = fileInput.disabled;
    const buttonWasDisabled = button && button.disabled;
    let refreshing = false;
    submitDocumentImport.pending = true;
    try {
        // Capture the file before disabling its form control.
        const formData = new FormData(form);
        fileInput.disabled = true;
        if (button) button.disabled = true;
        await WMS.api.postRaw(form.action, formData)
        .then(function(data) {
            if (data.status === 'success') {
                refreshing = true;
                showToast(data.msg || '导入成功', 'success', 3600);
                setTimeout(function(){ location.reload(); }, 900);
            } else {
                showToast(data.msg || '导入失败', 'danger', 5000);
            }
        });
    } catch (error) {
        showToast('导入失败：' + ((error && error.message) || '请求失败，请稍后重试'), 'danger', 5000);
    } finally {
        if (fileInput.files[0] === selectedFile) fileInput.value = '';
        if (!refreshing) {
            submitDocumentImport.pending = false;
            fileInput.disabled = wasDisabled;
            if (button) button.disabled = buttonWasDisabled;
        }
    }
}

function copyInOrder(id) {
    showConfirm('确定复制该入库单吗？系统会生成一张新的入库草稿，不会直接增加库存。', {title: '复制入库单'}).then(function(confirmed) {
        if (!confirmed) return;
        WMS.api.postRaw('/in_order/' + id + '/copy', {})
        .then(function(data) {
            if (data.status === 'success') {
                showToast(data.msg || '复制成功', 'success');
                setTimeout(function() {
                    window.location.href = data.redirect_url || ('/in_order/' + data.id);
                }, 500);
            } else {
                showToast(data.msg || '复制失败', 'danger', 5000);
            }
        })
        .catch(function(error) {
            showToast('复制失败：' + error.message, 'danger', 5000);
        });
    });
}
