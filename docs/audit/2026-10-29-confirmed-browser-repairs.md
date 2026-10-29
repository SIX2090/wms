# 2026-10-29 已确认浏览器问题统一修复

用户本次指令：把目前找出的问题全部修复。本批对应 **18 类尚未修复的确认观察**（17 类故障观察及 1 个不支持能力的误导入口），合并到下表 15 条 BUG 台账；不是18个新根因、18个按钮，也不宣称全站按钮已穷尽。历史已交付修复不重复计数。

| 台账 ID | 实测观察 | 本批行为 |
|---|---|---|
| BUG-2026-10-29-001 | FINAL29-ADD | 委外正常新增与重复复制因编号分支错误失败 |
| BUG-2026-10-29-002 | FINAL29-WAREHOUSE、FINAL29-STOCK | 委外复制和文件导入遗漏仓库且空仓库误显总库存 |
| BUG-2026-10-29-003 | FINAL29-NONE | 委外列表空联系人电话交期显示None |
| BUG-2026-10-29-004 | CHROME29-PRINT-BACK | 新标签页打印返回没有实际目标 |
| BUG-2026-10-29-005 | CHROME29-PRODUCT-IMPORT | 委外产品Excel导入确认时提示未配置接口 |
| BUG-2026-10-29-006 | CHROME29-DEPT-HEADER、CHROME29-DEPT-STATUS | 部门文件错误表头被接受且中文状态无法筛选 |
| BUG-2026-10-29-007 | EMP29-IMPORT-RAW-ERROR、EMP29-IMPORT-DEPT-LOSS | 员工导入损坏文件报英文且未知部门静默丢关联 |
| BUG-2026-10-29-008 | CONT29-DRILL-WAREHOUSE | 销售客户物料钻取丢失仓库及筛选条件 |
| BUG-2026-10-28-014-F01 | CONT29-PRINT-SCOPE | 独立销售打印仍遗漏所选仓库和查询期间 |
| BUG-2026-10-29-009 | CONT29-ASSET-CACHE | 报表脚本缓存一年使修复后普通刷新仍用旧版 |
| BUG-2026-10-29-010 | CONT29-PRICE-ENTRY | 价格维度关闭后订单执行仍显示价格分析入口 |
| BUG-2026-10-29-011 | BOM29-ACTIONS-LABEL | BOM栏目设置把选择列显示为技术字段actions |
| BUG-2026-10-29-012 | MAT29-LABEL-CANVAS | 默认物料标签画布字段空白且旧字段别名失配 |
| BUG-2026-10-29-013 | MAT29-LABEL-PREVIEW | 物料标签预览丢行且内容撑破指定标签尺寸 |
| BUG-2026-10-29-014 | BOM29-UNSUPPORTED-SHARE | BOM仍展示尚不支持的智能分享按钮 |

## 验证及边界

- 开工前核实 main 022bee6894bfa01a51c257ef22b841e16b957122，CI 40794846890、AI 40794846772 均 completed/success；Android 40791277115 在 3d17eb803a006f2abf14e6e091f1b7b24636c60a 成功，祖先及保护路径不变证明齐全。提交前匿名API403后经已连接GitHub工具逐页核对相同最新运行，没有将403当工作流失败或跳过未核实基线。
- 修前受影响模块1097 passed、21 skipped；增加部门相邻模块修前14 passed。新增61项回归在旧代码58 failed/3对照passed，外置源码回退后finally逐字节恢复，未使用stash、未放宽既有断言。修复后的定向补验233 passed。最终受影响与相邻回归1194 passed、21 skipped；规则A1–A14为0违规，JS非GET请求检查通过；目标提交及CI结果待本批后续补证。
- HTTP隔离冒烟119/119，明确排除两项密码写入。测试只连18082，数据库位于C:/wms_backups；外部网络、生产DB访问和真实打印代理保持隔离。
- Chrome实操确认：草稿补仓保存；产品Excel预览/导入/刷新后3行；其他仓QA-001库存2、QA-002库存3，未显示总账110/45；错误部门表头拒绝、重排表头+中文停用导入成功，新旧停用记录可筛选；损坏员工文件及未知部门均中文拒绝；BOM栏目显示“选择”并隐藏分享；销售实际物料下钻保留仓库5与日期、明细金额2，纸面仓库/期间可见；新开单据打印返回详情成功；标签五字段可见、默认单位别名正常、5行预览360×200px。
- 浏览器阶段前后stock_transaction、opening_stock、location_inventory、in_order、out_order、print_job、user表摘要均一致。仅隔离委外草稿2人工补仓及追加1行产品、增加测试部门与操作日志；未自动修历史错误数据。证据browser-boundary.json及before/after-browser.db。
- Chrome客户端下载ERR_BLOCKED_BY_CLIENT、原生确认控制超时属于尚未解决的浏览器环境限制，不能宣称由本批代码修复。真实出纸、相机、外部AI与全站未穷尽分支仍未验收；下载文件/生成Excel不等同真实打印完成。
- 生产需重启 WMS 服务生效。当前生产重启及公网目标版本验收待确认，不能把隔离站通过等同生产已生效。

本批所有日志与回退证据：`C:/wms_backups/all_confirmed_repairs_20261029/`。
