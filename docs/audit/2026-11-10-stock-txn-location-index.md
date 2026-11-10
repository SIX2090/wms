# 2026-11-10 生产库补建 `idx_stock_txn_location`

## 一、问题与成因

每次服务启动都输出：

```
WARNING - app - schema-check warning: 缺索引(仅告警): stock_transaction.idx_stock_txn_location；
按 docs/SCHEMA_UPGRADE.md 显式补齐
```

回溯：`BUG-2026-08-16-021` 在 2026-08-16 修掉了代码侧问题，`app/models/inventory.py` 的
`StockTransaction.__table_args__` 里加入了 `db.Index('idx_stock_txn_location', 'location')`，
用于加速「关闭库位管理」分支按 location 聚合仓库库存（否则全表扫）。

但代码定义不等于库里存在：生产实例以 `WMS_NO_DB_TOUCH=1` 启动，`auto_migrate_database()`
与全部启动期 DDL 被跳过（`app/app.py`），启动结构检查只做**只读**校验，缺普通性能索引
仅记录告警、不自动补建。因此这条索引从加入模型起就从未在生产库真正建立，告警每次启动
复现，属于「代码已修、库未跟上」的存量缺口。

## 二、变更前分析（只读预览）

按 `docs/SCHEMA_UPGRADE.md` 用官方工具预览，不手写 DDL：

```powershell
python scripts/upgrade_schema.py --db C:/wms/app/instance/inventory.db
```

输出：

```json
{
  "statements": ["CREATE INDEX idx_stock_txn_location ON stock_transaction (location)"],
  "blocked": []
}
```

即：待执行语句仅 1 条，无阻断项（不缺表、不缺列、无同名索引定义冲突）。
库规模 `inventory.db` 5.8 MB + WAL 2.9 MB，建索引为秒级，风险可控。

## 三、执行（按规范要求 停服 / 独占锁 / 新备份）

`docs/SCHEMA_UPGRADE.md` 规定：显式执行要求停服、独占锁及新备份。执行序列：

1. `schtasks /End /TN WMS-Warehouse` 停止 `WMS-Warehouse`，确认 `127.0.0.1:8080` 无监听；
2. 执行（工具内部先用只读连接算 plan，再用 SQLite backup API 建备份并做
   `PRAGMA integrity_check`，最后在写连接上提交全部 DDL）：

```powershell
python scripts/upgrade_schema.py --db C:/wms/app/instance/inventory.db `
  --apply --backup C:/wms_backups/schema_index_20261110/inventory-before-idx_stock_txn_location.db
```

输出：

```json
{"applied": 1, "backup": "C:\\wms_backups\\schema_index_20261110\\inventory-before-idx_stock_txn_location.db"}
```

3. `schtasks /Run /TN WMS-Warehouse` 按原部署入口恢复，约 70 秒后监听恢复。

## 四、验证

| 项目 | 结果 |
|---|---|
| 复预览 | `{"statements": [], "blocked": []}`，无待执行 |
| `sqlite_master` 定义 | `CREATE INDEX idx_stock_txn_location ON stock_transaction (location)` |
| 查询计划 | `SEARCH stock_transaction USING INDEX idx_stock_txn_location (location=?)`（原为全表扫） |
| `PRAGMA integrity_check` | `ok` |
| 启动日志 | `idx_stock_txn_location` 出现 **0 次**（此前每次启动 1 次） |
| 启动日志 ERROR/CRITICAL | 0 行 |
| 服务 | pid 7156 监听 `127.0.0.1:8080`，backend_sha `43866866`，checked_at 2026-11-10T20:12:23 |

## 五、备份与回退

- 备份：`C:/wms_backups/schema_index_20261110/inventory-before-idx_stock_txn_location.db`（5.8 MB，
  工具建，含完整性校验）
- 回退：如需撤销该索引，停服后 `DROP INDEX idx_stock_txn_location;` 即可，或按
  `scripts/restore_backup.py` 的独占锁流程恢复上述备份。索引是可加可去的纯性能对象，
  重建代价极低，不影响任何历史数据。

## 六、遗留（本次未处理，明确超出范围）

本次执行后启动仍输出 12 条**缺外键**告警（`employee.department_id`、`stock_transaction.warehouse_id`
等）。原因与索引不同：SQLite 无法对大表原地添加外键，需重建表并搬运数据；`docs/SCHEMA_UPGRADE.md`
已明确「既有库缺少外键沿用原检查的告警口径」，本工具不处理，属独立专项。

## 七、边界声明

- 本次仅执行 1 条 `CREATE INDEX`，未新增表、未新增列、未更新或删除任何业务行，未做回填。
- 未读取任何业务数据内容；预览与验证只读 `sqlite_master`、查询计划与完整性校验。
- 全程无自动迁移被打开：`WMS_NO_DB_TOUCH=1` 保持原状。
