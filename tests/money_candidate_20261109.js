// 与后端 Decimal(str(value)) / ROUND_HALF_UP 保持一致，避免先做二进制乘法。
(function (root) {
    'use strict';

    function parts(value) {
        const number = Number(value);
        if (!Number.isFinite(number) || Math.abs(number) > 9007199254740991)
            throw new RangeError('金额数量或单价超出可精确处理范围');
        const match = String(number).match(/^(-?)(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i);
        if (!match) throw new RangeError('金额数量或单价格式无效');
        return { negative: match[1] === '-', digits: match[2] + (match[3] || ''),
            scale: (match[3] || '').length - Number(match[4] || 0) };
    }

    function multiplyDigits(left, right) {
        const digits = Array(left.length + right.length).fill(0);
        for (let i = left.length - 1; i >= 0; i--) {
            for (let j = right.length - 1; j >= 0; j--) {
                digits[i + j + 1] += Number(left[i]) * Number(right[j]);
            }
        }
        for (let i = digits.length - 1; i > 0; i--) {
            digits[i - 1] += Math.floor(digits[i] / 10);
            digits[i] %= 10;
        }
        return digits.join('').replace(/^0+(?=\d)/, '');
    }

    function increment(value) {
        const digits = value.split('');
        for (let i = digits.length - 1; i >= 0; i--) {
            if (digits[i] !== '9') { digits[i] = String(Number(digits[i]) + 1); return digits.join(''); }
            digits[i] = '0';
        }
        return '1' + digits.join('');
    }

    function cents(left, right) {
        const a = parts(left), b = parts(right);
        let value = multiplyDigits(a.digits, b.digits);
        const scale = a.scale + b.scale - 2;
        if (scale > 0) {
            while (value.length <= scale) value = '0' + value;
            const cut = value.length - scale;
            const roundUp = value[cut] >= '5';
            value = value.slice(0, cut);
            if (roundUp) value = increment(value);
        } else if (scale < 0) {
            value += '0'.repeat(-scale);
        }
        value = value.replace(/^0+(?=\d)/, '');
        if (value.length > 16 || (value.length === 16 && value > '9007199254740991'))
            throw new RangeError('金额超出可精确处理范围');
        while (value.length < 3) value = '0' + value;
        const expected = value.slice(0, -2) + '.' + value.slice(-2);
        const result = Number(value + 'e-2');
        if (!Number.isFinite(result) || result.toFixed(2) !== expected)
            throw new RangeError('金额超出可精确处理范围');
        return (a.negative !== b.negative) ? -result : result;
    }

    root.WMSMoney = { product: cents, round: function (value) { return cents(value, 1); } };
})(window);
