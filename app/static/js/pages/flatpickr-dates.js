(function() {
    if (typeof window.flatpickr !== 'function') return;
    // 将所有原生 date 输入框替换为 flatpickr，显示中文格式 YYYY年MM月DD日
    // dateFormat 控制提交值（Y-m-d），altFormat 控制显示格式
    function initDateInputs(root) {
        var selector = 'input[type="date"]';
        var inputs = Array.from(root.querySelectorAll(selector));
        if (root.matches && root.matches(selector)) inputs.unshift(root);
        for (var i = 0; i < inputs.length; i++) {
            var el = inputs[i];
            if (el._flatpickr) continue;
            flatpickr(el, {
                dateFormat: 'Y-m-d',
                altInput: true,
                altFormat: 'Y年m月d日',
                locale: {
                    firstDayOfWeek: 1,
                    weekdays: { shorthand: ['日','一','二','三','四','五','六'], longhand: ['星期日','星期一','星期二','星期三','星期四','星期五','星期六'] },
                    months: { shorthand: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'], longhand: ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'] },
                    rangeSeparator: ' 至 ',
                    weekAbbreviation: '周',
                    scrollTitle: '滚动切换',
                    toggleTitle: '点击切换 12/24 小时制'
                }
            });
        }
    }
    initDateInputs(document);
    // 暴露给动态内容使用
    window.initFlatpickrDates = initDateInputs;
})();
