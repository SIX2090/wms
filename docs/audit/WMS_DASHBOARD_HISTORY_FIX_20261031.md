# 仪表盘与助手历史修复验收（2026-10-31）

基线73bf0bc9cde03e15271e7acb9e16ac2f1dd77daf，三项已确认问题：QA16-F01与QA18-F01/F02，登记BUG-2026-10-31-025至027。AI既有能力子修复AI-BROWSER-AUDIT-FIX-20261031-003。不开新能力、路由、权限、工具、模型、开关或迁移，不改库存写入。

- 仪表盘及独立AI环比分析：入/出库统计仅计completed，覆盖本月/上月金额和单数、趋势及月度图；保留仓库名称/编号及历史NULL边界。有显式状态筛选的明细报表保留查询草稿能力。
- 历史重复：新本地轮次拥有当前面板，失效待加载历史；恢复前检查已有上下文和DOM，列表/详情迟到响应均不覆盖新轮次；清理竞态同样保护。
- 历史标签：原始Markdown只交给addMessage渲染一次；用户内容走textContent，危险标签继续转义。不修改数据库中正确的原始内容。

验证证据C:/wms_backups/fix_dashboard_history_20261031_round19/。修前11模块209 passed；新增18锁修复后通过。最终15个受影响/相邻/文档模块319 passed（41项既有SQLAlchemy告警）。正确夹具物理换回两份旧产品文件后17 failed/1正对照passed，最后逐字节恢复；两次回退结果一致，无共享工作目录回退或stash。

如实记录中间结果：初次自造库存夹具缺request context，已修正夹具上下文。首次整组318 passed/1 failed为既有发送函数字节锁；保留原函数和原断言，将失效处理放在请求入口，重跑319全过。AI full首轮69/70，唯一失败是隔离副本漏Kotlin源文件；补齐受跟踪公开Android文本源后原verify_wms_bugs.py复验通过，70项逐项通过（69项整组证据+1项复验证据，未冒称第二次全量重跑），不修改检查或业务断言。原full_smoke_test.py经新隔离文件库和真实Flask路由桥接通过，登录仅为合成会话。规则0违规，裸非GET fetch及编码检查通过。

实际Chrome：仪表盘显示2张/12元，趋势数量6、月度金额12，排除待处理100个/200元；嵌入审计按钮经真实本地规则/SSE显示6/1/2/1，首次重开保留1条user+1条assistant。整页刷新从真实历史接口恢复仍为1轮，实际table元素1，正文无p/table标签；截图dashboard-fixed.png、history-fixed.png及browser-final-proof.json。一次导航/刷新控制超时后通过同一Chrome的新标签/新AX定位恢复，没有原生确认框、间接控制或外部模型调用。双仓A13/B20、库存流水、合成原始日志及配置前后一致。

生产数据库、账号、单据、库存和服务未操作，生产需重启 WMS 服务生效；前端资源需强刷。本批不把既有41项待验按钮自动全部关闭，真实登录、设备和外部AI不在合成验收范围。

有限清单按同一口径只关闭020的非空本地规则及可见结果/历史恢复分支：41→40，来源和逐项记录在本轮completed-current.json/pending-current.json；不是全系统按钮总数，也不代表外部模型质量或正常凭据验收。

代码已推送1eca191bd53cb52a0544019c54b6b5be2dacde2e；[AI验证](https://github.com/SIX2090/wms/actions/runs/41192232427)成功，[WMS CI](https://github.com/SIX2090/wms/actions/runs/41192232368)仅unit-tests-shard-2的一项文档行号契约失败：新增筛选使backfill_stock_txn_warehouse_id定义移至29805，INVENTORY_TRUTH.md引用未同步。隔离原测试复现1 failed/21 passed，保留原测试断言，同步该函数及相邻调用/NULL规则的三处文档引用；不修改库存逻辑。修正后完整22项通过，重新推送验收目标CI后再登记整体完成。

2026-10-31用户明确批准“允许本次最小修正推送并重新验收”：只提交三处文档引用和本验收记录，保留pre-commit，仅这次修正推送临时设置WMS_SKIP_CI_GATE=1，之后恢复门禁并验收新目标完整CI。此为用户批准的单次非绿修正例外，不作为全绿替代证据或后续跳过授权。相关文档契约整组114 passed、规则0违规、编码及diff检查通过。
