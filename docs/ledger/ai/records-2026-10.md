# AI 台账 · 记录归档 2026-10

> 本分片由 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md §16 完成记录小节及散装记录` 拆出（F4.4（2026-10-13））。
> 查询：`python scripts/query_ledger.py --task <ID>`。

---

### A3 台账登记收尾（2026-10-02 补登记）

A1/A2 代码早已推送，但本条一直停在「进行中」。2026-10-02 收尾时按 §五「台账 → 代码」双向对账，
发现**仅凭旧记录无法完成闭环**，补登记如下。

#### A3-3 派生工作全量清单（2026-10-02 二次对账补全）

**先纠正本节第一版（2026-10-02 早）的两处不实：**

1. **A3 并非「当天没做」**：`730c239f1`（2026-09-20T23:03Z，`docs(P1-7): ……atomic 3/3`）
   当日已把 §P1-7 整个小节（`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` +104 行）与
   `WMS_BUG_BASELINE.md` 主条目（+2 行）写入并推送；只是本表 A3 行从未从「进行中」
   翻到「已提交」，且其中登记的提交号不可解析（见 A3-1）。2026-10-02 的收尾
   = 补齐勘误、账实核对与派生清单，**而非「首次登记」**。
2. **派生工作不止三道闸**：按「2026-09-20 之后全部上游提交 × 采购退货关键词」重扫
   （`commits?since=2026-09-20` 全 213 条，命中 12 条），P1-7 的直接派生共 **9 项**
   （含三道闸），另有 1 项 P1-5 同族修复。此前只列了 3 项，遗漏 6 项。

| # | 日期 | 远端 SHA | 事项 | 基线登记 | 回归锁 |
|---|---|---|---|---|---|
| 1 | 09-21 | `855f9e743` | `BUG-2026-09-21-002`：详情页来源单链接补 `target=_blank`（BUG-2026-08-25-002 同根因复发，曾致 WMS CI unit-tests 红） | ✓ 行 | 模板改动（由 CI 拦截实证） |
| 2 | 09-22 | `43593b242` | `FEAT-2026-09-22-001`：采购管理 flyout 与出库单列表补「采购退货」入口——此前功能后端/模板/校验/测试齐全但**无任何可点入口，只能手敲 URL**（`base.html:2447`，复用 ASCII 别名避免中文 query 编码） | ✓ 行（2026-10-02 补登记） | 部分：T10/T11 锁列表页入口与新增页渲染；flyout 菜单项无独立断言（遗留子项） |
| 3 | 09-22 | `81be85304` | `BUG-2026-09-22-005`：批量完成路径 `batch_complete_out_order` 漏挂防超退闸 | ✓ 行 | `test_bug_2026_09_22_005_..._gate.py`（2） |
| 4 | 09-22 | `2027829be` | `BUG-2026-09-22-007`：明细级接口绕过防超退闸（接口层与保存层不对称） | ✓ 行 | `test_bug_2026_09_22_007_..._endpoints.py`（4） |
| 5 | 09-22 | `b0789ea32` | `BUG-2026-09-22-010`：手填单号可击穿来源的类型与状态校验（与选源接口口径不一致） | ✓ 行 | `test_bug_2026_09_22_010_..._status.py`（5） |
| 6 | 09-22 | `0e51fba9a` | `BUG-2026-09-22-013`：出库明细报表 `_filtered_out_detail_query` 无 `business_type` 条件，**采购退货出库混进领料明细报表虚增领料数量与金额**；且筛选白名单把该类型静默重置为空，用户连筛都筛不掉 | ✓ 行 | `test_bug_2026_09_22_013_..._isolation.py`（11→13） |
| 7 | 09-22 | `db9e51a0c` | `BUG-2026-09-22-014`：013 首版放行式白名单挡掉英文脏值 `requisition` 致 CI 红，默认口径改排除式（对未知值默认接受、失败模式多算可见，优于静默漏数） | ✓ 行 | 同上测试文件（增补 T5-b/T9） |
| 8 | 09-30 | `e3cb68d06` | `BUG-2026-09-30-002`：系统设置「采购退货必须关联订单」remark 仍写「为后续采购退货流程预留」，与已上线实现不符 | ✓（`###` 标题式） | 文案 1 行 |
| 9 | 09-30 | `f24908aa8` | **B2–B5 采购退货端到端闭环回归 9 项**（P0 计划 §二 M1 批次，补 005/007/010 未覆盖的表单路径端到端链路：选源口径/创建→草稿→完成全链路/跨单聚合/无来源拒绝/删除铁律/反提交回冲/双仓隔离/报表聚合）；当日本机全量 2986 passed | （仅基线 urllib3 条目顺带提及文件名） | `test_purchase_return_e2e_p0.py`（9） |

同族相邻（不计入 P1-7 派生，仅注明防漏看）：`cc731fa22`（09-22）
`BUG-2026-09-22-006` 批量完成**销售**退货入库单补防超退闸——P1-5 家族，
与 005 互为镜像（`sales_return_remaining_check` 对 `purchase_return_remaining_check`）。

**教训（应入流程）**：一个功能上线后暴露的派生工作，必须在**任务小节里维护动态清单**
（追加即可），不能只靠 `WMS_BUG_BASELINE.md` 按日期登记——基线按日期组织、按根因
检索尚可，但**按功能族归并**只有任务小节能做。本小节即按此补上。

#### A3-4 本次验证

第一批（2026-10-02 早，P1-7 本体 + 三道派生闸）：

```bash
WMS_ALLOW_INSECURE_COOKIE=1 python -m pytest \
  tests/verify_purchase_return_outbound.py \
  tests/test_bug_2026_09_22_005_batch_complete_purchase_return_gate.py \
  tests/test_bug_2026_09_22_007_purchase_return_item_endpoints.py \
  tests/test_bug_2026_09_22_010_purchase_return_source_type_status.py -q
```

**29 passed**（21.51s），即本任务与其三道派生闸**当前仍然全绿**——台账里 2026-09-20 记的
「18 passed」在今天重跑仍成立，不是过期结论被抄进完成记录。

第二批（2026-10-02 晚，配合 A3-3 全量清单补跑端到端与报表隔离）：

```bash
WMS_ALLOW_INSECURE_COOKIE=1 python -m pytest \
  tests/test_purchase_return_e2e_p0.py \
  tests/test_bug_2026_09_22_013_out_detail_business_type_isolation.py -q
```

**22 passed**（16.16s）——B2–B5 端到端 9 项 + 013/014 报表隔离 13 项当前仍全绿。
两批合计 **51 passed**，覆盖 P1-7 本体与全部有回归锁的派生项；
无锁的 #2（菜单入口）已在 `base.html:2446-2447` 代码核对命中。

## AI-PROMPT-V2-2026-10-04 —— 应用内 system prompt 结构化升级 + 运行时截断/意图契约修复（2026-10-04）

**问题**：①`legacy-v1` system prompt 中英混杂、红线是口号无行为指令、R5「低置信度回退人工」未注入运行时、无输出契约；②`providers.py` `user_message[:1000]` 硬截断，长文本后半段静默丢失且模型不知数据不全；③`call_llm_intent` 只设 `json_object` 不定义字段，输出字段漂移靠运气。

**改动**（2 个 atomic action）：
1. `app/ai/prompts.py`：注册 `copilot-v2` 并切换 `CURRENT_PROMPT_VERSION`（红线落到行为指令 + R5 回退义务 + 输出契约；保留全部被 BUG-2026-08-12-003 锁定的关键词与英文安全边界，版本槽可秒级回滚）。文件头补「改 prompt 必跑 golden 回归并记录命中率」纪律。commit `0ee74a1`。
2. `app/ai/providers.py`：新增 `truncate_ai_user_message`（首尾保留 + 显式截断标记「不得假设数据完整/禁止臆造」）替换两处硬截断；`call_llm_intent` 追加 `_INTENT_OUTPUT_CONTRACT`（字段契约 + unknown 兜底 + 高风险拒答 + 禁止猜测）。commit `2bc5b04`。

**验证**：新增 `verify_ai_prompt_copilot_v2.py` 5 项 + `verify_ai_providers_truncation.py` 6 项；红线回归 4 项；`verify_ai_platform_foundations.py` PASS；AI 子系统相关 129 passed / 0 failed；`lint_wms_rules.py --staged` 0 违规。

**遗留子项**：①app.py 4 处 `[:1000]`（聊天/意图链路）未动——行号被 `test_inventory_truth_line_refs.py` 锚定，新增 import 会移位，需单行替换方案另行立项；②v2 上线后首个golden 回归周期需在 `provider_evaluation` 按 prompt_hash 对比 legacy-v1/copilot-v2 的识别命中率并回填本条目；③生产需重启 WMS 服务生效（R3）。

