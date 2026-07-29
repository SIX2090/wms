# WMS 菜单与按钮命令与实际业务不符检查报告

## 一、检查范围
- 系统：WMS（仓库管理系统）
- 菜单数：74 个
- 涉及页面：61 个菜单项可访问页面
- 服务地址：http://127.0.0.1:8080
- 验证脚本：`/tmp/audit/`

## 二、检查方法
1. 从 `app/templates/base.html` 提取所有菜单（flyout-link + nav-link）
2. 从 `app/app.py` 提取所有路由（587 个）
3. 每个菜单 URL 通过 HTTP GET 验证状态码
4. 抓取每个页面的 `<title>` 和 `<h1>/<h2>` 与菜单文字比对
5. 抓取每个页面的业务按钮（data-action、表单 action、endpoints）
6. 比对按钮命令的 endpoint 是否对应真实路由

## 三、检查结果

### 3.1 总体数据
| 维度 | 数量 |
| --- | --- |
| 菜单总数 | 74 |
| 可访问页面（HTTP 200） | 74 |
| 路由不存在的菜单 | 0 |
| 表单/endpoint 不存在的 | 0 |
| 菜单与页面标题明显不符 | 17 |
| 按钮命令与实际业务不符 | （见下） |

### 3.2 菜单与实际页面 title 名称不符（共 17 个）

| # | 菜单文字 | URL | 实际页面 title | 性质 |
| --- | --- | --- | --- | --- |
| 1 | 采购订单 | /purchase_order/add | 新增采购单 | 同物异名 |
| 2 | 采购入库 | /in_order/add | 新增入库单 | 同物异名 |
| 3 | 采购申请列表 | /purchase_request | 采购申请管理 | 列表/管理 |
| 4 | 采购订单列表 | /purchase_order?view=list | 采购单管理 | 列表/管理 |
| 5 | 采购入库明细 | /in_order?type=purchase_in | 采购入库单 | 明细/单 |
| 6 | 采购入库明细报表 | /report/view/in_detail | 入库明细报表 | "采购"前缀缺失 |
| 7 | 销售订单列表 | /sales | 销售订单管理 | 列表/管理 |
| 8 | 直接销售出库 | /out_order/add?type=sale | 新增销售单 | **标题极具迷惑性**（用户会以为是"新建销售订单"） |
| 9 | 产品入库 | /in_order/add?type=product | 新增入库单 | 同物异名 |
| 10 | 其他入库单 | /other_in_order/add | 新增入库单 | 同物异名（应该显示"新增其他入库单"） |
| 11 | 入库明细 | /in_order | 入库单 | 明细/单 |
| 12 | 其他入库明细 | /other_in_order | 其他入库单 | 明细/单 |
| 13 | BOM管理 | /bom | BOM清单管理 | 名称不一致 |
| 14 | 委外管理 | /subcontract | 委外加工单 | 名称不一致 |
| 15 | 物料管理 | /material | 物料档案 | 名称不一致 |
| 16 | 系统设置 | /system_settings | 系统参数 | 名称不一致 |
| 17 | AI质量运营 | /ai/business_quality | AI业务质量运营看板 | 名称不一致 |

### 3.3 按钮命令与实际业务不符（按页面维度）

#### A. 全局一致性问题：每个页面都存在一个"未真正渲染的 copy 按钮注释"
- 位置：`app/templates/base.html` 第 167~168 行（JavaScript 注释）
- 内容：`// 格式: <button data-action="copy" data-id="{order.id}">复制</button>`
- 现状：该注释作为格式说明保留在 `<script>` 块内，**没有真正生成按钮**，但任何静态分析工具都会误判
- 影响：低（实际不影响用户，但代码异味）

#### B. 业务按钮的 data-action 与实际业务不一致（多页面共有）

| 页面 | 按钮 | 实际 data-action | 实际处理结果 |
| --- | --- | --- | --- |
| 销售订单列表 | 删除已选 | batch_delete | 实际只调 `/sales/batch_delete`，仅对草稿可删除，confirm 提示"只有草稿状态可删除"，文字与行为基本匹配 ✓ |
| 销售出库列表 | 删除已选 | batch_delete | 实际只调 `/out_order/batch_delete`，提示"确认删除选中的出库单？删除后无法恢复" ✓ |

#### C. 列表页"完成已选"按钮（in_order 列表独有）
- 位置：/in_order?type=purchase_in
- 按钮文字："完成已选"
- 对应 endpoint：/in_order/batch_complete
- 业务含义：批量完成入库单
- 验证结果：路由存在，处理逻辑正确 ✓

#### D. 工具栏新增但未实现 import/export
| 页面 | 工具栏按钮 | 处理函数 | 备注 |
| --- | --- | --- | --- |
| 委外管理 | 批量导入 | submitImportForm | 通过 `/subcontract/import` ✓ |
| 物料管理 | 批量导入 | submitImportForm | 通过 `/material/import` ✓ |
| BOM管理 | 批量导入 | submitImportForm | 通过 `/bom/import` ✓ |
| 期初库存 | 批量导入 | 实际上该页无导入 form action | **不一致** ✗ |

#### E. /opening_stock 页面 (期初库存) 表单 action 错误
- 抓取到的 form action: `/opening_stock`
- POST 到 `/opening_stock` 会触发 GET handler，方法不被允许
- 实际上该页通过 `/opening_stock/batch_save` 提交
- **按钮命令与实际业务不符** ✗

#### F. AI 助手面板提示语被误识别为"按钮"
- 几乎每个页面都有一组 AI 提示文字："取消任务"、"继续执行"、"Agent巡检"、"今日优先级"、"提交前检查"、"解释异常"、"送货单入库"、"表格转单"、"微信成领料"、"异常工作台"、"采购工作台"、"补货请购"、"供应商画像"、"催交话术"、"销售工作台"、"生成出库草稿"、"客户画像"、"催发货话术"、"微信成销售出库"、"GPT识别微信"、"基础体检"、"修复清单"、"导入助手"、"系统体检"、"系统清单"、"权限助手"、"日志审计"、"软件建议"、"AI路线图"、"任务清单"、"打开功能"、"识图自检"等
- 这些是 AI 助手面板的快捷词（点击后会自动填入 AI 对话框），**不是**真正的业务按钮
- 但视觉上与按钮无差异（同样的 chip 样式），可能误导用户以为这些是"功能按钮"

## 四、结论

### 4.1 菜单与实际页面不符
- **共 17 个**菜单的"文字"与"实际页面 title"不严格对应
- 其中"直接销售出库 → 新增销售单"是最严重的（用户会以为"新建销售订单"菜单失效）
- 其它主要是"列表/管理"、"入库单/入库明细"的用词差异，**功能正确但菜单名与页面名不统一**

### 4.2 按钮命令与实际业务不符
- **1 个**真实问题：/opening_stock 页面表单 action 写为 `/opening_stock`，与实际业务 `batch_save` 路由不一致
- **1 处**误报：base.html 中 `data-action="copy"` 注释
- **多处**AI 助手提示语视觉上像按钮，需在 UI 上与功能按钮区分

### 4.3 建议修复优先级
1. P0：期初库存 form action 错误（/opening_stock）
2. P1：修正"直接销售出库"页面 title 为"新增直接销售出库单"
3. P2：统一菜单与页面 title 命名（17 处）
4. P3：清理 base.html 中残留的 `data-action="copy"` 注释或补齐实现
5. P3：AI 助手提示语样式上与功能按钮区分
