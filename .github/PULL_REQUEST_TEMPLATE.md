## 改动说明

<!-- 简述本次 PR 做了什么，为什么做 -->

## 改动类型

<!-- 请勾选所有适用项 -->

- [ ] 新功能（feature）
- [ ] BUG 修复（bugfix）
- [ ] 重构（refactor）
- [ ] 文档（docs）
- [ ] 测试（test）
- [ ] 性能优化（perf）
- [ ] 其他（chore）

## 关联 BUG

<!-- 如果修复了某个 BUG，关联它；没有则填"无" -->

- BUG ID: BUG-YYYY-MM-DD-NNN
- 描述：

## 测试覆盖

<!-- 必须勾选至少一项，否则 CI 会拒绝合并 -->

- [ ] 已跑 `python3 scripts/lint_wms_rules.py`（0 违规）
- [ ] 已跑 `python3 scripts/verify_wms_bugs.py`（86/86 PASS）
- [ ] 已跑 `pytest tests/ -q`（90/90 PASS）
- [ ] 已跑 `python3 scripts/full_smoke_test.py`（121/121 PASS）
- [ ] 已加新的回归测试（描述在下方）

新增测试：

## Checklist

- [ ] 我的代码遵循了 [DEVELOPMENT_RULES.md](../DEVELOPMENT_RULES.md)
- [ ] 我加了必要的注释（特别是复杂逻辑）
- [ ] 我没有遗留 `console.log` / `debugger` / `print` / `eval`
- [ ] 我没有把 secrets 提交到仓库
- [ ] 我更新了相关文档（如果有）

## 截图 / 录屏

<!-- 如果是 UI 改动，附上 before/after 截图 -->

## 风险评估

<!-- 这段代码上线后可能出什么问题？rollback 计划？ -->

## 备注

<!-- 给 review 的人看的信息 -->
