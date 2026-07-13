# WMS 仓库管理系统 BUG 分析报告

**分析日期**: 2026-06-27 | **状态**: 仅分析未改代码

> 历史报告说明（2026-07-13）：本文保留用于追溯最初风险发现，不代表当前代码状态。当前是否存在回归以 `WMS_BUG_BASELINE.md` 和 `scripts\verify_wms_bugs.py` 的最新结果为准。

---

## 一、严重级别定义

| 级别 | 说明 |
|------|------|
| 严重 | 数据丢失/系统崩溃/安全漏洞 |
| 高 | 功能无法正常使用 |
| 中 | 功能异常但有替代方案 |
| 低 | 轻微问题 |

---

## 二、BUG 清单

### BUG-001 [严重] 数据库提交失败仍返回成功

**文件**: app.py 多处分段

**问题**: commit() 失败后 rollback()，但未 return 错误，继续执行 log_operation() 并返回 {"status":"success"}。用户看到成功提示但数据实际未保存。

**典型代码**:
```python
try:
    db.session.commit()
except Exception as e:
    db.session.rollback()
    app.logger.error(f'数据库操作失败: {e}')
log_operation(...)  # commit失败还在执行！
return jsonify({'status': 'success', 'msg': 'BOM 新增成功'})
```

**影响范围**: BOM新增/编辑、物料管理、订单处理等全部核心业务。

---

### BUG-002 [严重] 库存扣减缺少事务隔离

**文件**: app.py ~3429行

**问题**: 出库操作分两步：先 deduct_stock() 再 update_location_inventory()，中间无行锁。并发场景下另一请求可读到未扣减的库存导致超卖。第二步失败时库存已扣无法回滚。

```python
ok, msg = deduct_stock(...)
# ← 并发窗口
ok, msg = update_location_inventory(...)  # 失败时库存已扣无法回滚
```

---

### BUG-003 [高] 委外收货数量双倍计算

**文件**: app.py ~4095行

**问题**: db.session.add(receive_item) 后 SQLAlchemy autoflush 将数据刷入库，后续 sum 查询重复计算本次收货量，导致订单状态提前变为 completed。

---

### BUG-004 [中] 仓库/部门新增缺异常处理

**文件**: app.py ~5217行、5455行

**问题**: add_warehouse() 和 add_department() 的 commit() 无 try-except，数据库约束冲突时 500 错误。

---

### BUG-005 [中] 物料复制编码生成逻辑缺陷

**文件**: app.py ~5031行

**问题**: generate_material_copy_code() 硬编码编码格式为 6 位(前3分类+后3流水)，后3位流水最大 999，超出抛异常。

---

### BUG-006 [中] 期初库存调整无并发锁

**文件**: app.py ~4751行

**问题**: _apply_opening_stock_balance() 先读旧值再算差后写，无 with_for_update()，并发时库存计算错误。

---

### BUG-007 [中] 批量删除物料逻辑矛盾

**文件**: app.py ~5873行

**问题**: 先检查引用跳过有业务数据的物料(fail_count++)，紧接着执行 delete() 删同一批关联数据——第2步是死代码，第1步的检查无意义。

---

### BUG-008 [高] 全局 confirmResolver 竞态条件

**文件**: app.js 第2行、65行

**问题**: 全局变量存 Promise.resolve，多次调用 confirmDialog() 时后一次覆盖前一次，前一个 Promise 永不 resolve，UI 卡死。

```javascript
let confirmResolver = null;
function confirmDialog(message, options) {
    return new Promise(function(resolve) {
        confirmResolver = resolve;  // 覆盖上一个！
    });
}
```

---

### BUG-009 [中] 事件监听器泄漏

**文件**: app.js ~1187行

**问题**: setupDetailTable() 每次往 document 上加 click 监听器，从不移除。切换标签页导致监听器累积。

---

### BUG-010 [中] ExcelTable 事件监听器未清理

**文件**: excel-table.js ~46行

**问题**: cloneNode + replaceChild 替换单元格，旧节点上事件监听器泄漏。

---

### BUG-011 [低] ExcelImportExport 重复创建模态框

**文件**: excel-import-export.js ~97行

**问题**: createImportModal() 每次插入同名模态框 HTML，不检查 #excelImportModal 是否已存在。

---

### BUG-012 [低] 客户端导出跳过列逻辑错误

**文件**: excel-import-export.js ~339行

**问题**: 用 index===0 硬编码跳过头列，列顺序变动后导出列错位。

---

## 三、安全漏洞

### VULN-001 [严重] 打印模板HTML净化失败返回空

**文件**: utils.py ~355行

**问题**: sanitize_print_html() 异常时 return ''，用户看到空白打印页，无任何错误提示。

### VULN-002 [高] 模板中使用 |safe 过滤器

**文件**: 多个HTML模板

**问题**: 渲染用户输入时用 |safe 不转义，可触发存储型XSS。

### VULN-003 [高] 部分表单缺少CSRF Token

**文件**: login.html 等独立页面

**问题**: 不继承 base.html 的页面需手动配置 CSRF token，可能遗漏。

### VULN-004 [中] 密码策略不一致

**文件**: app.py ~4118行

**问题**: validate_password_strength() 要求8位+数字+字母，但某些修改密码路径可能未调用。

---

## 四、配置问题

### CONF-001 [严重] SECRET_KEY 未强制配置

**文件**: config.py 第34行

**问题**: SECRET_KEY = os.environ.get('SECRET_KEY') 可能为 None。

### CONF-002 [中] 开发配置泄露风险

**文件**: config.py ~107行

**问题**: DevelopmentConfig 开启 DEBUG=True + SQLALCHEMY_ECHO=True。

### CONF-003 [中] Cookie Secure 标志未启用

**文件**: config.py ~101行

**问题**: SESSION_COOKIE_SECURE = False。

### CONF-004 [中] SQLite 并发限制

**文件**: config.py ~38行

**问题**: 生产用 SQLite，写入串行化不适合高并发 WMS 场景。

---

## 五、数据统计

| 严重级别 | 数量 | 占比 |
|---------|------|------|
| 严重 | 4 | 20% |
| 高 | 4 | 20% |
| 中 | 7 | 35% |
| 低 | 2 | 10% |
| **总计** | **20** | **100%** |

| 类别 | 数量 |
|------|------|
| 后端BUG | 7 |
| 前端BUG | 5 |
| 安全漏洞 | 4 |
| 配置问题 | 4 |

---

## 六、优先修复建议

**严重(立即)**: BUG-001/002、VULN-001、CONF-001
**高(近期)**: BUG-003/008、VULN-002/003
**中(计划)**: BUG-004/005/006/007/009/010、CONF-002/003/004
**低(可选)**: BUG-011/012
