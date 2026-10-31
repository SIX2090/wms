    (function() {
        const button = document.getElementById('aiAssistantButton');
        const panel = document.getElementById('aiAssistantPanel');
        const closeButton = document.getElementById('aiAssistantClose');
        const clearButton = document.getElementById('aiHistoryClear');
        const form = document.getElementById('aiAssistantForm');
        const input = document.getElementById('aiAssistantInput');
        const messages = document.getElementById('aiAssistantMessages');
        const pasteButton = document.getElementById('aiPasteButton');
        const uploadButton = document.getElementById('aiUploadButton');
        const imageInput = document.getElementById('aiImageInput');
        const pendingWrap = document.getElementById('aiPendingAttachments');
        if (!button || !panel || !form || !input || !messages) return;
        const pendingImages = [];
        const maxImages = 3;
        const maxImageBytes = 10 * 1024 * 1024;
        const chatHistory = [];

        // BUG-2026-07-28-016 修复：滚动到底自动收起浮窗 + 用户偏好记忆
        const HIDE_KEY = 'wms_ai_hide_floating';
        let isHidden = false;
        try { isHidden = localStorage.getItem(HIDE_KEY) === '1'; } catch (e) {}
        if (isHidden) {
            button.style.display = 'none';
        }
        // 在按钮上额外加一个小 × 用于彻底隐藏
        if (!document.getElementById('aiAssistantHideBtn')) {
            const hideBtn = document.createElement('span');
            hideBtn.id = 'aiAssistantHideBtn';
            hideBtn.title = '隐藏 AI 浮窗（24h）';
            hideBtn.innerHTML = '<i class="bi bi-eye-slash"></i>';
            hideBtn.style.cssText = 'position:absolute;top:-6px;right:-6px;width:18px;height:18px;' +
                'background:#94a3b8;color:#fff;border-radius:50%;font-size:10px;line-height:18px;' +
                'text-align:center;cursor:pointer;display:none;';
            button.style.position = 'relative';
            button.appendChild(hideBtn);
            hideBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                try { localStorage.setItem(HIDE_KEY, '1'); } catch (err) {}
                button.style.display = 'none';
                const tip = document.createElement('div');
                tip.textContent = 'AI 浮窗已隐藏，刷新页面可恢复';
                tip.style.cssText = 'position:fixed;right:20px;bottom:20px;background:#1f2937;color:#fff;' +
                    'padding:8px 12px;border-radius:6px;font-size:12px;z-index:99999;';
                document.body.appendChild(tip);
                setTimeout(function() { tip.remove(); }, 2500);
            });
            button.addEventListener('mouseenter', function() { hideBtn.style.display = 'block'; });
            button.addEventListener('mouseleave', function() { hideBtn.style.display = 'none'; });
        }
        // 滚动到底部时按钮缩小并半透明
        let scrollTimer = null;
        window.addEventListener('scroll', function() {
            if (scrollTimer) return;
            scrollTimer = setTimeout(function() {
                scrollTimer = null;
                const scrolled = window.scrollY + window.innerHeight;
                const total = document.documentElement.scrollHeight;
                if (total > window.innerHeight + 200 && scrolled >= total - 80) {
                    button.style.transform = 'scale(0.6)';
                    button.style.opacity = '0.4';
                } else {
                    button.style.transform = '';
                    button.style.opacity = '';
                }
            }, 100);
        }, { passive: true });
        const maxHistory = 20;
        let isSending = false;
        let pendingUploadPrompt = '';
        if (window.self !== window.top) {
            button.style.display = 'none';
            panel.remove();
            return;
        }

        function setBusy(busy) {
            isSending = !!busy;
            panel.classList.toggle('is-busy', isSending);
            input.disabled = isSending;
        }



        function renderMarkdown(text) {
            if (!text) return '';
            let src = escapeHtml(text);
            // 浠ｇ爜鍧?```lang\ncode```
            const blocks = [];
            src = src.replace(/```(\w*)\n?([\s\S]*?)```/g, function(m, lang, code) {
                const idx = blocks.length;
                blocks.push('<pre><code>' + code.replace(/\n$/, '') + '</code></pre>');
                return '\u0000BLOCK' + idx + '\u0000';
            });
            // 行内代码 `code`
            const inlines = [];
            src = src.replace(/`([^`\n]+)`/g, function(m, code) {
                const idx = inlines.length;
                inlines.push('<code>' + code + '</code>');
                return '\u0000INLINE' + idx + '\u0000';
            });
            const lines = src.split('\n');
            const out = [];
            let i = 0;
            let inList = null;
            let tableRows = [];
            let inTable = false;

            function flushList() {
                if (inList) { out.push('</' + inList + '>'); inList = null; }
            }
            function flushTable() {
                if (!inTable) return;
                if (tableRows.length) {
                    out.push('<table>');
                    tableRows.forEach(function(row, ri) {
                        out.push('<tr>');
                        row.forEach(function(cell) {
                            if (ri === 0) out.push('<th>' + cell.trim() + '</th>');
                            else out.push('<td>' + cell.trim() + '</td>');
                        });
                        out.push('</tr>');
                    });
                    out.push('</table>');
                }
                tableRows = [];
                inTable = false;
            }

            while (i < lines.length) {
                const line = lines[i];
                if (line.indexOf('\u0000BLOCK') === 0) {
                    flushList(); flushTable();
                    out.push(line.replace(/\u0000BLOCK(\d+)\u0000/, function(m, idx) { return blocks[parseInt(idx)]; }));
                    i++; continue;
                }
                if (/^\s*\|.+\|\s*$/.test(line)) {
                    flushList();
                    if (/^\s*\|[\s:|-]+\|\s*$/.test(line)) { i++; continue; }
                    const cells = line.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|');
                    tableRows.push(cells);
                    inTable = true;
                    i++; continue;
                } else {
                    flushTable();
                }
                const h = line.match(/^(#{1,4})\s+(.*)$/);
                if (h) {
                    flushList();
                    const level = h[1].length;
                    out.push('<h' + level + '>' + h[2].trim() + '</h' + level + '>');
                    i++; continue;
                }
                if (/^&gt;\s?/.test(line)) {
                    flushList();
                    out.push('<blockquote>' + line.replace(/^&gt;\s?/, '') + '</blockquote>');
                    i++; continue;
                }
                if (/^(\*\*\*|---|___)\s*$/.test(line)) {
                    flushList();
                    out.push('<hr>');
                    i++; continue;
                }
                if (/^\s*[-*+]\s+/.test(line)) {
                    if (inList !== 'ul') { flushList(); out.push('<ul>'); inList = 'ul'; }
                    out.push('<li>' + line.replace(/^\s*[-*+]\s+/, '') + '</li>');
                    i++; continue;
                }
                if (/^\s*\d+\.\s+/.test(line)) {
                    if (inList !== 'ol') { flushList(); out.push('<ol>'); inList = 'ol'; }
                    out.push('<li>' + line.replace(/^\s*\d+\.\s+/, '') + '</li>');
                    i++; continue;
                }
                if (!line.trim()) {
                    flushList();
                    i++; continue;
                }
                flushList();
                out.push('<p>' + line + '</p>');
                i++;
            }
            flushList(); flushTable();
            let html = out.join('\n');
            html = html.replace(/\u0000INLINE(\d+)\u0000/g, function(m, idx) { return inlines[parseInt(idx)]; });
            // 加粗 **text**
            html = html.replace(/\*\*([^\*\n]+)\*\*/g, '<strong>$1</strong>');
            return html;
        }

        function copyText(text) {
            if (!text) return;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).catch(function() {});
            } else {
                const area = document.createElement('textarea');
                area.value = text;
                document.body.appendChild(area);
                area.select();
                try { document.execCommand('copy'); } catch (error) {}
                area.remove();
            }
        }

        function addMessage(text, type, attachments, useMarkdown, toolStatus, dataSource) {
            const node = document.createElement('div');
            node.className = 'ai-message ' + (type || 'assistant');

            // 添加工具状态卡片
            if (toolStatus) {
                const statusCard = renderToolStatus(toolStatus);
                node.appendChild(statusCard);
            }

            const contentEl = document.createElement('div');
            contentEl.className = 'ai-message-content';
            if (type === 'user') {
                contentEl.textContent = text;
            } else {
                // 助手消息默认渲染 Markdown，除非明确禁用。
                contentEl.innerHTML = useMarkdown === false ? escapeHtml(text) : renderMarkdown(text);
            }
            node.appendChild(contentEl);

            // 添加数据来源显示
            if (dataSource && type !== 'user') {
                const sourceEl = renderDataSource(dataSource);
                node.appendChild(sourceEl);
            }
            const copyButton = document.createElement('button');
            copyButton.type = 'button';
            copyButton.className = 'ai-message-copy';
            copyButton.title = '复制';
            copyButton.innerHTML = '<i class="bi bi-copy"></i>';
            copyButton._aiText = text;
            copyButton.addEventListener('click', function(event) {
                event.stopPropagation();
                copyText(this._aiText);
            });
            node.appendChild(copyButton);
            if (attachments && attachments.length) {
                const thumbs = document.createElement('div');
                thumbs.className = 'ai-attachment-thumbs';
                attachments.forEach(function(item) {
                    const thumb = document.createElement('div');
                    thumb.className = 'ai-attachment-thumb';
                    const img = document.createElement('img');
                    img.src = item.data_url;
                    img.alt = item.name || '图片';
                    thumb.appendChild(img);
                    thumbs.appendChild(thumb);
                });
                node.appendChild(thumbs);
            }
            messages.appendChild(node);
            messages.scrollTop = messages.scrollHeight;
            return node;
        }

        // 渲染工具执行状态卡片
        function renderToolStatus(status) {
            const card = document.createElement('div');
            card.className = 'ai-tool-status ai-tool-status-' + (status.state || 'running');

            const icons = {
                'query': '<i class="bi bi-search"></i>',
                'executing': '<i class="bi bi-gear-fill"></i>',
                'confirm': '<i class="bi bi-check-circle-fill"></i>',
                'failed': '<i class="bi bi-x-circle-fill"></i>',
                'running': '<i class="bi bi-arrow-repeat"></i>'
            };

            const labels = {
                'query': '查询中',
                'executing': '执行中',
                'confirm': '待确认',
                'failed': '执行失败',
                'running': '处理中'
            };

            card.innerHTML = `
                <div class="ai-tool-status-header">
                    ${icons[status.state] || icons['running']}
                    <span class="ai-tool-status-label">${labels[status.state] || '处理中'}</span>
                    ${status.tool_name ? `<span class="ai-tool-name">${escapeHtml(status.tool_name)}</span>` : ''}
                </div>
                ${status.message ? `<div class="ai-tool-status-message">${escapeHtml(status.message)}</div>` : ''}
                ${status.progress ? `<div class="ai-tool-progress"><div class="progress-bar" style="width: ${status.progress}%"></div></div>` : ''}
            `;

            return card;
        }

        // 渲染数据来源标签
        function renderDataSource(source) {
            const badge = document.createElement('span');
            badge.className = 'ai-data-source ai-data-source-' + (source.type || 'rule');

            const icons = {
                'realtime': '<i class="bi bi-database"></i>',
                'rule': '<i class="bi bi-gear"></i>',
                'llm': '<i class="bi bi-robot"></i>'
            };

            const labels = {
                'realtime': '实时查询',
                'rule': '系统规则',
                'llm': 'AI解释'
            };

            badge.innerHTML = `${icons[source.type] || icons['rule']} ${labels[source.type] || '系统规则'}`;

            if (source.timestamp) {
                badge.title = '数据时间：' + new Date(source.timestamp).toLocaleString('zh-CN');
            }

            return badge;
        }

        // 渲染反馈按钮
        function renderFeedbackButtons(messageId) {
            const container = document.createElement('div');
            container.className = 'ai-feedback-buttons';
            container.innerHTML = `
                <button type="button" class="ai-feedback-btn" data-feedback="helpful" data-message-id="${messageId}" title="有帮助">
                    <i class="bi bi-hand-thumbs-up"></i>
                </button>
                <button type="button" class="ai-feedback-btn" data-feedback="recognition_error" data-message-id="${messageId}" title="识别错误">
                    <i class="bi bi-eye-slash"></i>
                </button>
                <button type="button" class="ai-feedback-btn" data-feedback="match_error" data-message-id="${messageId}" title="匹配错误">
                    <i class="bi bi-link-45deg"></i>
                </button>
                <button type="button" class="ai-feedback-btn" data-feedback="permission_error" data-message-id="${messageId}" title="权限错误">
                    <i class="bi bi-shield-x"></i>
                </button>
            `;

            // 绑定反馈事件
            container.querySelectorAll('.ai-feedback-btn').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    const feedback = this.dataset.feedback;
                    const msgId = this.dataset.messageId;
                    submitFeedback(msgId, feedback);

                    // 标记已反馈
                    container.querySelectorAll('.ai-feedback-btn').forEach(function(b) {
                        b.disabled = true;
                    });
                    this.classList.add('active');
                });
            });

            return container;
        }

        // 提交反馈
        // AI-FEEDBACK-LOOP-001：端点 POST /api/ai/feedback（ai_bp.feedback_create）读取的字段是
        // rating（helpful/not_helpful）+ error_type + ai_message_id；此前的
        // message_id/feedback_type/timestamp 与端点完全错配，按钮 100% 返回 400，
        // 反馈从未入库。 helpful → 正面评价；其余按钮 → not_helpful + 对应 error_type。
        function submitFeedback(messageId, feedbackType) {
            WMS.api.postRaw('/api/ai/feedback', {
                rating: feedbackType === 'helpful' ? 'helpful' : 'not_helpful',
                error_type: feedbackType === 'helpful' ? null : feedbackType,
                ai_message_id: messageId
            }).then(function(data) {
                if (data.status === 'success') {
                    showToast('感谢您的反馈', 'success');
                } else {
                    showToast(data.msg || '反馈提交失败', 'danger');
                }
            }).catch(function(error) {
                showToast(error.message || '反馈提交失败', 'danger');
                console.error('反馈提交失败:', error);
            });
        }

        // 渲染文档任务中心
        function renderDocumentTaskCenter(tasks) {
            const container = document.createElement('div');
            container.className = 'ai-document-task-center';

            if (!tasks || tasks.length === 0) {
                container.innerHTML = '<div class="ai-task-empty">暂无文档识别任务</div>';
                return container;
            }

            let tasksHtml = '<div class="ai-task-list">';
            tasks.forEach(function(task) {
                const statusIcons = {
                    'pending': '<i class="bi bi-clock"></i>',
                    'processing': '<i class="bi bi-arrow-repeat"></i>',
                    'completed': '<i class="bi bi-check-circle"></i>',
                    'failed': '<i class="bi bi-x-circle"></i>'
                };

                const statusLabels = {
                    'pending': '等待处理',
                    'processing': '识别中',
                    'completed': '已完成',
                    'failed': '识别失败'
                };

                tasksHtml += `
                    <div class="ai-task-item ai-task-${task.status}">
                        <div class="ai-task-header">
                            ${statusIcons[task.status] || statusIcons['pending']}
                            <span class="ai-task-title">${escapeHtml(task.title || '文档识别')}</span>
                            <span class="ai-task-status">${statusLabels[task.status] || '未知'}</span>
                        </div>
                        <div class="ai-task-meta">
                            <span class="ai-task-time">${new Date(task.created_at).toLocaleString('zh-CN')}</span>
                            ${task.file_name ? `<span class="ai-task-file">${escapeHtml(task.file_name)}</span>` : ''}
                        </div>
                        ${task.status === 'completed' ? `
                            <div class="ai-task-actions">
                                <button type="button" class="btn btn-sm btn-outline-primary" data-task-id="${task.id}" data-action="view">查看结果</button>
                                <button type="button" class="btn btn-sm btn-primary" data-task-id="${task.id}" data-action="create-draft">生成草稿</button>
                            </div>
                        ` : ''}
                        ${task.status === 'failed' ? `
                            <div class="ai-task-actions">
                                <button type="button" class="btn btn-sm btn-outline-secondary" data-task-id="${task.id}" data-action="retry">重试</button>
                            </div>
                        ` : ''}
                    </div>
                `;
            });
            tasksHtml += '</div>';

            container.innerHTML = tasksHtml;

            // 绑定任务操作事件
            container.querySelectorAll('[data-action]').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    const taskId = this.dataset.taskId;
                    const action = this.dataset.action;
                    handleDocumentTaskAction(taskId, action);
                });
            });

            return container;
        }

        // 处理文档任务操作
        // BUG-2026-09-25-002 修复：三个按钮原先都指向不存在的路由，点击必然 404。
        //   view        → /ai/document/<id>                （不存在）
        //   create-draft→ /ai/document/<id>/create-draft   （不存在）
        //   retry       → POST /api/ai/document/<id>/retry （不存在，且期望 JSON 响应）
        // 后端真实路由为 /ai/document_jobs/<id>（详情页，app.py:20547）与
        // POST /ai/document_jobs/<id>/retry（表单式，app.py:20593，返回 redirect+flash
        // 而非 JSON，因此必须用表单提交而非 fetch，否则拿不到结果也跳不过去）。
        function handleDocumentTaskAction(taskId, action) {
            if (action === 'view') {
                window.open('/ai/document_jobs/' + taskId, '_blank');
            } else if (action === 'create-draft') {
                window.location.href = '/ai/document_jobs/' + taskId;
            } else if (action === 'retry') {
                // 表单式 POST，随响应跟随 redirect 并由后端 flash 提示结果
                var form = document.createElement('form');
                form.method = 'POST';
                form.action = '/ai/document_jobs/' + taskId + '/retry';
                form.style.display = 'none';
                var csrf = document.querySelector('meta[name="csrf-token"]');
                if (csrf) {
                    var input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'csrf_token';
                    input.value = csrf.content;
                    form.appendChild(input);
                }
                document.body.appendChild(form);
                form.submit();
            }
        }

        function renderPendingImages() {
            if (!pendingWrap) return;
            pendingWrap.innerHTML = '';
            pendingWrap.classList.toggle('has-items', pendingImages.length > 0);
            pendingImages.forEach(function(item, index) {
                const thumb = document.createElement('div');
                thumb.className = 'ai-attachment-thumb';
                const img = document.createElement('img');
                img.src = item.data_url;
                    img.alt = item.name || '图片';
                const remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'ai-attachment-remove';
                remove.textContent = '×';
                remove.addEventListener('click', function() {
                    pendingImages.splice(index, 1);
                    renderPendingImages();
                });
                thumb.appendChild(img);
                thumb.appendChild(remove);
                pendingWrap.appendChild(thumb);
            });
        }

        function readFileAsDataUrl(file) {
            return new Promise(function(resolve, reject) {
                const reader = new FileReader();
                reader.onload = function(event) { resolve(event.target.result); };
                reader.onerror = function() { reject(new Error('图片读取失败')); };
                reader.readAsDataURL(file);
            });
        }

        function loadImageElement(dataUrl) {
            return new Promise(function(resolve, reject) {
                const img = new Image();
                img.onload = function() { resolve(img); };
                img.onerror = function() { reject(new Error('图片解析失败')); };
                img.src = dataUrl;
            });
        }

        function canvasToDataUrl(canvas, mimeType, quality) {
            return new Promise(function(resolve) {
                if (canvas.toBlob) {
                    canvas.toBlob(function(blob) {
                        if (!blob) {
                            resolve(canvas.toDataURL(mimeType, quality));
                            return;
                        }
                        const reader = new FileReader();
                        reader.onload = function(event) { resolve(event.target.result); };
                        reader.onerror = function() { resolve(canvas.toDataURL(mimeType, quality)); };
                        reader.readAsDataURL(blob);
                    }, mimeType, quality);
                } else {
                    resolve(canvas.toDataURL(mimeType, quality));
                }
            });
        }

        function prepareImageAttachment(file) {
            return readFileAsDataUrl(file).then(function(originalUrl) {
                if (!/^image\/(jpeg|png|webp)$/i.test(file.type || '')) {
                    return {
                        name: file.name || 'clipboard-image',
                        mime_type: file.type,
                        size: file.size,
                        data_url: originalUrl
                    };
                }
                return loadImageElement(originalUrl).then(function(img) {
                    const maxSide = 1800;
                    const scale = Math.min(1, maxSide / Math.max(img.naturalWidth || img.width, img.naturalHeight || img.height));
                    if (scale >= 1 && file.size <= 2 * 1024 * 1024) {
                        return {
                            name: file.name || 'clipboard-image',
                            mime_type: file.type,
                            size: file.size,
                            data_url: originalUrl
                        };
                    }
                    const canvas = document.createElement('canvas');
                    canvas.width = Math.max(1, Math.round((img.naturalWidth || img.width) * scale));
                    canvas.height = Math.max(1, Math.round((img.naturalHeight || img.height) * scale));
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    return canvasToDataUrl(canvas, 'image/jpeg', 0.86).then(function(dataUrl) {
                        return {
                            name: file.name || 'clipboard-image',
                            mime_type: 'image/jpeg',
                            size: Math.round(dataUrl.length * 0.75),
                            data_url: dataUrl
                        };
                    });
                }).catch(function() {
                    return {
                        name: file.name || 'clipboard-image',
                        mime_type: file.type,
                        size: file.size,
                        data_url: originalUrl
                    };
                });
            });
        }

        function addImageFile(file) {
            return new Promise(function(resolve) {
                if (!file || !file.type || !file.type.startsWith('image/')) {
                    resolve(false);
                    return;
                }
                if (pendingImages.length >= maxImages) {
                    addMessage('最多一次上传 ' + maxImages + ' 张图片。', 'assistant');
                    resolve(false);
                    return;
                }
                if (file.size > maxImageBytes) {
                    addMessage('图片太大，请上传 10MB 以内的清晰原图。', 'assistant');
                    resolve(false);
                    return;
                }
                prepareImageAttachment(file).then(function(attachment) {
                    pendingImages.push(attachment);
                    renderPendingImages();
                    resolve(true);
                }).catch(function() {
                    addMessage('图片读取失败，请重新选择图片。', 'assistant');
                    resolve(false);
                });
            });
        }

        function addImageFiles(files) {
            return Promise.all(Array.from(files || []).map(addImageFile)).then(function(results) {
                return results.some(Boolean);
            });
        }

        function openUrl(url, label) {
            if (!url) return;
            if (window.WmsTabs) {
                window.WmsTabs.open(url, label || 'AI助手');
            } else {
                window.location.href = url;
            }
        }

        function renderCards(cards) {
            (cards || []).forEach(function(card) {
                const node = document.createElement('div');
                node.className = 'ai-card';
                const title = document.createElement('div');
                title.className = 'ai-card-title';
                title.textContent = card.title || (card.order_no ? ((card.type || '单据') + ' ' + card.order_no) : ((card.code || '') + ' ' + (card.name || '')));
                const meta = document.createElement('div');
                meta.className = 'ai-card-meta';
                if (card.stock !== undefined) {
                    meta.textContent = '库存：' + card.stock + (card.unit ? ' ' + card.unit : '') + (card.spec ? '，规格：' + card.spec : '');
                } else if (card.quantity !== undefined) {
                    meta.textContent = '数量：' + card.quantity;
                } else if (card.meta) {
                    meta.textContent = card.meta;
                } else if (card.status || card.date) {
                    meta.textContent = [card.status, card.date].filter(Boolean).join('，');
                } else {
                    meta.textContent = card.url || '';
                }
                node.appendChild(title);
                node.appendChild(meta);
                if (card.url) {
                    node.style.cursor = 'pointer';
                    node.addEventListener('click', function() { openUrl(card.url, title.textContent); });
                }
                messages.appendChild(node);
            });
            messages.scrollTop = messages.scrollHeight;
        }

        function renderActions(actions) {
            if (!actions || !actions.length) return;
            const wrap = document.createElement('div');
            wrap.className = 'ai-actions';
            actions.forEach(function(action) {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'ai-action';
                btn.textContent = action.label || '打开';
                btn.addEventListener('click', function() {
                    if (action.upload && imageInput) {
                        pendingUploadPrompt = action.prompt || '识别送货单图片并生成采购入库单草稿';
                        imageInput.click();
                    } else if (action.prompt) {
                        sendAssistantMessage(action.prompt, []);
                    } else {
                        openUrl(action.url, action.label);
                    }
                });
                wrap.appendChild(btn);
            });
            messages.appendChild(wrap);
            messages.scrollTop = messages.scrollHeight;
        }

        function createAIRequestId() {
            if (window.crypto && typeof window.crypto.randomUUID === 'function') {
                return window.crypto.randomUUID();
            }
            return 'ai-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 14);
        }

        function sendNonStreaming(text, attachments, requestId) {
            historyLoaded = true;
            historyVersion += 1;
            requestId = requestId || createAIRequestId();
            setBusy(true);
            const loading = addMessage('正在处理...', 'assistant', null, false);
            const activeContext = window.WmsTabs && window.WmsTabs.getActiveContext ? window.WmsTabs.getActiveContext() : null;
            WMS.api.postRaw('/api/ai/warehouse_assistant', {
                request_id: requestId,
                message: text,
                attachments: attachments,
                page_url: activeContext ? activeContext.url : (window.location.pathname + window.location.search),
                page_title: activeContext ? activeContext.title : document.title
            })
            .then(function(data) {
                loading.remove();
                setBusy(false);
                if (data.status !== 'success') {
                    addMessage(data.msg || '处理失败', 'assistant');
                    return;
                }
                addMessage(data.reply || '已处理', 'assistant');
                renderCards(data.cards);
                renderActions(data.actions);
            })
            .catch(function(error) {
                loading.remove();
                setBusy(false);
                addMessage('处理失败：' + error.message, 'assistant');
            });
        }

        function tryStreamChat(text, requestId) {
            historyLoaded = true;
            historyVersion += 1;
            requestId = requestId || createAIRequestId();
            setBusy(true);
            const loading = addMessage('正在处理...', 'assistant', null, false);
            const contentEl = loading.querySelector('.ai-message-content');
            const cursor = document.createElement('span');
            cursor.className = 'ai-streaming-cursor';
            contentEl.appendChild(cursor);
            const copyBtn = loading.querySelector('.ai-message-copy');
            let buffer = '';
            let finished = false;
            let pendingCards = null;
            let pendingActions = null;

            function finalize() {
                if (finished) return;
                finished = true;
                setBusy(false);
                cursor.remove();
                if (!buffer.trim()) {
                    loading.remove();
                    addMessage('没有收到回复，请稍后重试。', 'assistant');
                    return;
                }
                contentEl.innerHTML = renderMarkdown(buffer);
                if (copyBtn) copyBtn._aiText = buffer;
                chatHistory.push({role: 'user', content: text});
                chatHistory.push({role: 'assistant', content: buffer});
                while (chatHistory.length > maxHistory) chatHistory.shift();
                messages.scrollTop = messages.scrollHeight;
                // 渲染业务卡片/动作（业务意图在流式通道内执行后追加的事件）
                if (pendingCards) renderCards(pendingCards);
                if (pendingActions) renderActions(pendingActions);
            }

            const activeContext = window.WmsTabs && window.WmsTabs.getActiveContext ? window.WmsTabs.getActiveContext() : null;
            WMS.api.postResponse('/api/ai/chat/stream', {
                request_id: requestId,
                message: text,
                history: chatHistory,
                page_url: activeContext ? activeContext.url : (window.location.pathname + window.location.search),
                page_title: activeContext ? activeContext.title : document.title
            }).then(function(res) {
                const ct = res.headers.get('content-type') || '';
                if (ct.includes('application/json')) {
                    return res.json().then(function(data) {
                        loading.remove();
                        setBusy(false);
                    addMessage(data.msg || '处理失败', 'assistant');
                    });
                }
                if (!res.body || !res.body.getReader) {
                    loading.remove();
                    setBusy(false);
                    sendNonStreaming(text, [], createAIRequestId());
                    return;
                }
                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                let pending = '';
                function read() {
                    return reader.read().then(function(result) {
                        if (result.done) { finalize(); return; }
                        pending += decoder.decode(result.value, {stream: true});
                        const lines = pending.split('\n');
                        pending = lines.pop();
                        for (const line of lines) {
                            const trimmed = line.trim();
                            if (!trimmed.startsWith('data: ')) continue;
                            try {
                                const evt = JSON.parse(trimmed.slice(6));
                                if (evt.type === 'token' && evt.content) {
                                    buffer += evt.content;
                                    contentEl.innerHTML = renderMarkdown(buffer);
                                    contentEl.appendChild(cursor);
                                    messages.scrollTop = messages.scrollHeight;
                                } else if (evt.type === 'cards') {
                                    pendingCards = evt.content;
                                } else if (evt.type === 'actions') {
                                    pendingActions = evt.content;
                                } else if (evt.type === 'done') {
                                    buffer = evt.content || buffer;
                                    finalize();
                                    return;
                                } else if (evt.type === 'error') {
                                    loading.remove();
                                    setBusy(false);
                                    addMessage(evt.content || '处理失败', 'assistant');
                                    return;
                                }
                            } catch(e) {}
                        }
                        return read();
                    });
                }
                return read();
            }).catch(function(error) {
                loading.remove();
                setBusy(false);
                addMessage('处理失败：' + error.message, 'assistant');
            });
        }

        // AI_FIX_TASK: AI-BROWSER-AUDIT-FIX-20261031-003
        let historyLoaded = false;
        let historyVersion = 0;
        function restoreHistory() {
            // AI-ASSISTANT-HISTORY-001：面板首次打开时从 DB 恢复最近活跃会话，
            // 刷新/重启后对话不再丢失。失败静默（老行为：空面板开新对话）。
            if (historyLoaded) return;
            historyLoaded = true;
            if (chatHistory.length || messages.querySelector('.ai-message')) return;
            const version = historyVersion;
            WMS.api.getRaw('/api/ai/conversations?limit=1')
                .then(function(data) {
                    if (version !== historyVersion) return;
                    if (!data || data.status !== 'success' || !data.conversations || !data.conversations.length) return;
                    var conv = data.conversations[0];
                    if (conv.status !== 'active') return;
                    return WMS.api.getRaw('/api/ai/conversations/' + conv.id + '?limit=20')
                        .then(function(detail) {
                            if (version !== historyVersion || chatHistory.length || messages.querySelector('.ai-message')) return;
                            if (!detail || detail.status !== 'success' || !detail.messages || !detail.messages.length) return;
                            detail.messages.forEach(function(m) {
                                if (m.role !== 'user' && m.role !== 'assistant') return;
                                addMessage(m.content, m.role, null, m.role === 'assistant');
                            });
                            // 恢复的消息同步进内存 chatHistory，供多轮上下文拼接
                            detail.messages.forEach(function(m) {
                                if (m.role !== 'user' && m.role !== 'assistant') return;
                                chatHistory.push({role: m.role, content: m.content});
                            });
                            while (chatHistory.length > maxHistory) chatHistory.shift();
                            messages.scrollTop = messages.scrollHeight;
                        });
                })
                .catch(function() {});
        }
        button.addEventListener('click', function() {
            panel.classList.toggle('open');
            if (panel.classList.contains('open')) {
                restoreHistory();
                input.focus();
            }
        });
        closeButton.addEventListener('click', function() {
            panel.classList.remove('open');
        });
        if (clearButton) {
            clearButton.addEventListener('click', function() {
                historyLoaded = true;
                historyVersion += 1;
                WMS.api.post('/api/ai/chat/clear', {})
                    .then(function() {
                        chatHistory.length = 0;
                        addMessage('已清空对话历史，可以开始新的对话。', 'assistant');
                    })
                    .catch(function(error) {
                        chatHistory.length = 0;
                        addMessage('服务器对话未清空，仅清空本地上下文：' + (error.message || '请求失败'), 'assistant');
                    });
            });
        }
        if (uploadButton && imageInput) {
            uploadButton.addEventListener('click', function() {
                pendingUploadPrompt = '';
                imageInput.click();
            });
            imageInput.addEventListener('change', function() {
                const prompt = pendingUploadPrompt;
                pendingUploadPrompt = '';
                addImageFiles(imageInput.files).then(function(hasImage) {
                    imageInput.value = '';
                    if (hasImage && prompt) {
                        const attachments = pendingImages.slice();
                        pendingImages.length = 0;
                        renderPendingImages();
                        sendAssistantMessage(prompt, attachments);
                    }
                });
            });
        }
        if (pasteButton) {
            pasteButton.addEventListener('click', function() {
                if (!navigator.clipboard || !navigator.clipboard.readText) {
                    input.focus();
                    return;
                }
                navigator.clipboard.readText().then(function(text) {
                    if (text) {
                        input.value = input.value ? (input.value + ' ' + text) : text;
                        input.focus();
                    }
                }).catch(function() {
                    input.focus();
                });
            });
        }
        document.addEventListener('paste', function(event) {
            if (!panel.classList.contains('open')) return;
            const items = event.clipboardData && event.clipboardData.items ? Array.from(event.clipboardData.items) : [];
            const imageItems = items.filter(function(item) { return item.type && item.type.startsWith('image/'); });
            if (!imageItems.length) return;
            imageItems.forEach(function(item) {
                const file = item.getAsFile();
                if (file) addImageFile(file);
            });
            event.preventDefault();
        });
        function sendAssistantMessage(text, attachments) {
            if (isSending) return;
            attachments = attachments || [];
            if (!text && !attachments.length) return;
            if (!text && attachments.length) text = '请分析这张图片';
            addMessage(text, 'user', attachments);
            const requestId = createAIRequestId();
            if (attachments.length) {
                sendNonStreaming(text, attachments, requestId);
            } else {
                tryStreamChat(text, requestId);
            }
        }
        // AI_FIX_TASK: AI-BROWSER-AUDIT-FIX-20261031-002
        window.WmsAiAssistant = {
            ask: function(text) {
                if (typeof text !== 'string' || !text.trim()) return false;
                if (isSending) {
                    showToast('AI助手正在处理，请稍后重试', 'warning');
                    return false;
                }
                panel.classList.add('open');
                sendAssistantMessage(text.trim(), []);
                return true;
            }
        };
        messages.addEventListener('click', function(event) {
            const btn = event.target.closest('.ai-suggestion');
            if (!btn || isSending) return;
            const prompt = (btn.getAttribute('data-prompt') || btn.textContent || '').trim();
            if (!prompt) return;
            panel.classList.add('open');
            input.value = '';
            if (btn.getAttribute('data-ai-upload') === 'delivery-note' && imageInput) {
                pendingUploadPrompt = prompt;
                imageInput.click();
                return;
            }
            sendAssistantMessage(prompt, []);
        });
        form.addEventListener('submit', function(event) {
            event.preventDefault();
            if (isSending) return;
            const text = input.value.trim();
            if (!text && !pendingImages.length) return;
            const attachments = pendingImages.slice();
            pendingImages.length = 0;
            renderPendingImages();
            input.value = '';
            sendAssistantMessage(text, attachments);
        });
    })();
