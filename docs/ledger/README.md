# 台账分片库（F4.4 拆分）

> F4.4（2026-10-13）：`WMS_BUG_BASELINE.md`（923KB）与 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（624KB）
> 的历史记录部分按月拆分为分片，主文件只保留规则、规范与索引。目的：git diff 噪声下降、
> 任一条目 ≤2 次文件读取可得。

## 结构

| 目录 | 内容 | 来源章节 |
|---|---|---|
| `ai/completions-YYYY-MM.md` | AI 台账完成记录表（按月） | AI 台账 §8 |
| `ai/records-YYYY-MM.md` | AI 台账完成记录小节归档（按月） | AI 台账 §16 及尾部散装小节 |
| `ai/INDEX.md` | AI 台账条目 → 分片索引 | — |
| `bugs/fixed-YYYY-MM.md` | BUG 基线「已修复并纳入回归」归档（按月） | BUG 基线 |
| `bugs/history-YYYY-MM.md` | BUG 基线「历史登记区」归档（按月） | BUG 基线 |
| `bugs/entries-YYYY-MM.md` | BUG 详情小节归档（按月） | BUG 基线门禁段及尾部 |
| `bugs/INDEX.md` | BUG 基线条目 → 分片索引 | — |

## 登记规则

- **新 AI 任务完成条目** → 追加到 `ai/completions-<当月>.md` 表尾（无则新建），并更新 `ai/INDEX.md`。
- **新 BUG 详情小节** → 写入 `bugs/entries-<当月>.md`（必须含「生效确认」字段，A13 门禁），并更新 `bugs/INDEX.md`。
- **新 BUG 修复登记** → 追加到 `bugs/fixed-<当月>.md` 表尾。
- 主文件 `WMS_BUG_BASELINE.md` / `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 只承载规则/规范/索引，不再追加记录。

## 查询

```bash
python scripts/query_ledger.py --task BUG-2026-10-05-001   # BUG 详情
python scripts/query_ledger.py --task F3.14                # AI 任务条目
python scripts/query_ledger.py --list                      # 列出所有分片
```
