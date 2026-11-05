/* Product receipt header: reuse the authenticated contract master search. */
(function(global) {
    'use strict';

    function bind(input) {
        if (input.dataset.productContractBound === '1') return;
        var form = input.closest('form');
        var project = form && form.querySelector('[name="project_name"]');
        if (!project) return;
        input.dataset.productContractBound = '1';
        var version = 0;
        var timer = null;
        var autoProject = '';
        var applying = false;
        var contractEdited = false;

        function lookup(delayed) {
            clearTimeout(timer);
            var requestVersion = ++version;
            var keyword = input.value.trim();
            if (!keyword) return;
            if (project.value.trim() && !contractEdited) return;
            function current() {
                return version === requestVersion && input.isConnected !== false &&
                    input.value.trim() === keyword;
            }
            function search() {
                global.WMS.api.getContracts(keyword).then(function(data) {
                    if (!current()) return;
                    if (!data || !Array.isArray(data.contracts)) throw new Error('Invalid contract response');
                    var matches = data.contracts.filter(function(contract) {
                        return contract && typeof contract.contract_no === 'string' &&
                            contract.contract_no.trim().toLowerCase() === keyword.toLowerCase();
                    });
                    if (matches.length !== 1) return;
                    if (typeof matches[0].project_name !== 'string') throw new Error('Invalid project response');
                    input.value = matches[0].contract_no;
                    project.value = matches[0].project_name;
                    autoProject = project.value;
                    contractEdited = false;
                    applying = true;
                    try { project.dispatchEvent(new Event('input', {bubbles: true})); }
                    finally { applying = false; }
                }).catch(function() {
                    if (current() && typeof global.showToast === 'function') {
                        global.showToast('合同查询失败，可重试或手工填写工程名称', 'danger');
                    }
                });
            }
            if (delayed) timer = setTimeout(search, 200);
            else search();
        }

        input.addEventListener('input', function() {
            contractEdited = true;
            if (autoProject && project.value === autoProject) project.value = '';
            autoProject = '';
            lookup(true);
        });
        input.addEventListener('change', function() { lookup(false); });
        input.addEventListener('blur', function() { lookup(false); });
        input.addEventListener('focus', function() { if (!project.value.trim()) lookup(false); });
        project.addEventListener('input', function() {
            if (applying) return;
            ++version;
            clearTimeout(timer);
            autoProject = '';
            contractEdited = false;
        });
        if (input.value.trim() && !project.value.trim()) lookup(false);
    }

    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('[data-product-contract]').forEach(bind);
    });
})(window);
