/**
 * WMS 统一 HTTP 客户端
 *
 * 解决问题：业务代码直接调 fetch/csrfFetch/$.ajax 各有各的写法，
 * 经常忘记带 CSRF token，或者忘记处理 res.status === 'success' 的判断。
 *
 * 用法：
 *   WMS.api.get('/api/categories')
 *       .then(items => console.log(items))
 *       .catch(err => showToast(err.message, 'danger'));
 *
 *   WMS.api.post('/material/delete', { ids: [1, 2, 3] })
 *       .then(res => showToast('删除成功', 'success'))
 *       .catch(err => showToast(err.message, 'danger'));
 *
 *   WMS.api.put('/material/123', { name: '...' })
 *   WMS.api.delete('/material/123')
 *
 * 特性：
 * - 自动从 <meta name="csrf-token"> 读取 token 并加到 X-CSRFToken 头
 * - 自动 JSON 解析
 * - 自动判断 res.status === 'success'，否则 reject
 * - 自动处理 401/419 会话过期
 * - 统一错误对象：{ status, code, message, data }
 */
(function(global) {
    'use strict';

    if (global.WMS && global.WMS.api) {
        // 防止重复定义
        return;
    }

    // ==================== 内部工具 ====================

    /**
     * 读取 CSRF token（从 meta 标签或隐藏域）
     */
    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) return meta.content;
        var hidden = document.querySelector('input[name="csrf_token"]');
        return hidden ? hidden.value : '';
    }

    /**
     * 构造请求头
     */
    function buildHeaders(extraHeaders, hasBody) {
        var headers = {
            'X-Requested-With': 'XMLHttpRequest'
        };
        if (hasBody && !(extraHeaders && extraHeaders['Content-Type'])) {
            headers['Content-Type'] = 'application/json';
        }
        if (extraHeaders) {
            for (var k in extraHeaders) {
                if (Object.prototype.hasOwnProperty.call(extraHeaders, k)) {
                    headers[k] = extraHeaders[k];
                }
            }
        }
        // 注入 CSRF token
        var token = getCsrfToken();
        if (token && !headers['X-CSRFToken']) {
            headers['X-CSRFToken'] = token;
        }
        return headers;
    }

    /**
     * 构造请求体
     */
    function buildBody(data) {
        if (data == null) return undefined;
        if (data instanceof FormData) return data;
        return JSON.stringify(data);
    }

    /**
     * 统一错误处理：401/419 会话过期
     */
    var sessionExpiredShown = false;
    function handleSessionExpired() {
        if (sessionExpiredShown) return;
        sessionExpiredShown = true;
        if (global.confirm('登录已过期或会话失效，请重新登录。点击确定跳转到登录页面。')) {
            global.location.href = '/login';
        } else {
            setTimeout(function() { sessionExpiredShown = false; }, 5000);
        }
    }

    /**
     * 统一请求入口
     */
    function request(method, url, options, raw) {
        options = options || {};
        var data = options.data;
        var query = options.query;
        var isFormData = data instanceof FormData;
        var headers = buildHeaders(options.headers, data != null && !isFormData);
        var body = buildBody(data);

        // 拼接 query string
        if (query) {
            var qs = [];
            for (var k in query) {
                if (Object.prototype.hasOwnProperty.call(query, k)) {
                    qs.push(encodeURIComponent(k) + '=' + encodeURIComponent(query[k]));
                }
            }
            if (qs.length) {
                url += (url.indexOf('?') >= 0 ? '&' : '?') + qs.join('&');
            }
        }

        return fetch(url, {
            method: method,
            credentials: 'same-origin',
            headers: headers,
            body: body,
            signal: options.signal
        })
        .then(function(response) {
            // 401/419: 会话过期
            if (response.status === 401 || response.status === 419) {
                handleSessionExpired();
                throw {
                    status: response.status,
                    code: 'SESSION_EXPIRED',
                    message: '登录已过期，请重新登录'
                };
            }
            // 非 2xx
            if (!response.ok) {
                return response.json().catch(function() {
                    throw {
                        status: response.status,
                        code: 'HTTP_ERROR',
                        message: '请求失败 (' + response.status + ')'
                    };
                }).then(function(err) {
                    throw {
                        status: response.status,
                        code: err && err.code ? err.code : 'HTTP_ERROR',
                        message: (err && err.msg) ? err.msg : ('请求失败 (' + response.status + ')'),
                        data: err
                    };
                });
            }
            // 下载调用方需要响应头和未消费的二进制正文；仍先执行统一HTTP/会话检查。
            if (raw === 'response') return response;
            return response.json();
        })
        .then(function(res) {
            // BUG-2026-10-17-014-F06：raw 模式返回完整响应（含 status/page/total_pages），
            // 供需要分页元数据的调用方使用；默认模式仍自动解包 data。
            if (raw) return res;
            // 业务状态判断
            if (res && res.status === 'success') {
                return res.data !== undefined ? res.data : res;
            }
            // 业务失败
            var err = {
                status: 200,
                code: (res && res.code) ? res.code : 'BUSINESS_ERROR',
                message: (res && res.msg) ? res.msg : '操作失败',
                data: res
            };
            throw err;
        });
    }

    // ==================== 公共 API ====================

    var api = {
        get: function(url, options) {
            return request('GET', url, options);
        },
        // 返回完整响应体（不解包 data），用于需要分页元数据的场景
        getRaw: function(url, options) {
            return request('GET', url, options, true);
        },
        postRaw: function(url, data, options) {
            options = options || {};
            options.data = data;
            return request('POST', url, options, true);
        },
        // 返回未消费的成功Response；调用方须核对Content-Type并处理业务错误正文。
        postResponse: function(url, data, options) {
            options = options || {};
            options.data = data;
            return request('POST', url, options, 'response');
        },
        post: function(url, data, options) {
            options = options || {};
            options.data = data;
            return request('POST', url, options);
        },
        put: function(url, data, options) {
            options = options || {};
            options.data = data;
            return request('PUT', url, options);
        },
        patch: function(url, data, options) {
            options = options || {};
            options.data = data;
            return request('PATCH', url, options);
        },
        delete: function(url, data, options) {
            options = options || {};
            if (data) options.data = data;
            return request('DELETE', url, options);
        },
        // 兼容旧风格：csrfFetch(url, options) -> WMS.api.csrfFetch(...)
        csrfFetch: function(url, options) {
            return request(options && options.method ? options.method : 'POST', url, options);
        },
        // 合同档案关键词搜索（合同编号 / 工程名称）
        getContracts: function(keyword) {
            return this.get('/api/contracts', { query: { keyword: keyword || '' } });
        },
        // 暴露给业务代码的辅助函数
        getCsrfToken: getCsrfToken
    };

    // 挂载到全局
    global.WMS = global.WMS || {};
    global.WMS.api = api;
})(window);
