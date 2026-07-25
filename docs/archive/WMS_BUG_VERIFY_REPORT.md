# WMS 系统 BUG 核验与修复报告

**核验日期**: 2026-06-27 | **状态**: 历史归档

> 本报告是早期逐项核验记录，不再作为当前修复清单。当前结论以根目录 `WMS_BUG_BASELINE.md` 为准。
**核验方式**: 逐条读取实际源代码进行验证
**核验结论**: 仅分析，未修改任何代码

> 历史报告说明（2026-07-13）：本文记录 2026-06-27 当时的逐项核验，不应作为当前缺陷清单。当前基线见 `WMS_BUG_BASELINE.md`，执行结果见 `scripts\verify_wms_bugs.py`。

---

## 一、核验结果总览

| 编号 | 原报告级别 | 核验结论 | 真实级别 |
|------|-----------|---------|---------|
| BUG-001 | 严重 | ✅ 真实存在 | 严重 |
| BUG-002 | 严重 | ✅ 真实存在 | 严重 |
| BUG-003 | 高 | ❌ 误报 | 不存在 |
| BUG-004 | 中 | ✅ 真实存在 | 中 |
| BUG-005 | 中 | ✅ 真实存在（已有部分fallback） | 中 |
| BUG-006 | 中 | ✅ 真实存在 | 中 |
| BUG-007 | 中 | ⚠️ 部分误报 | 低（死代码） |
| BUG-008 | 高 | ❌ 误报 | 不存在 |
| BUG-009 | 中 | ✅ 真实存在 | 中 |
| BUG-010 | 中 | ✅ 真实存在 | 中 |
| BUG-011 | 低 | ✅ 真实存在 | 低 |
| BUG-012 | 低 | ✅ 真实存在 | 低 |
| VULN-001 | 严重 | ✅ 真实存在 | 中（已有防御） |
| VULN-002 | 高 | ⚠️ 部分误报 | 低（已有sanitize） |
| VULN-003 | 高 | ⚠️ 待证实 | 低 |
| VULN-004 | 中 | ⚠️ 待证实 | 低 |
| CONF-001 | 严重 | ✅ 真实存在 | 严重 |
| CONF-002 | 中 | ✅ 真实存在 | 中 |
| CONF-003 | 中 | ⚠️ 部分误报 | 低（生产已修正） |
| CONF-004 | 中 | ✅ 真实存在 | 中 |

**核验后真实BUG统计**:
- 真实存在: 15 个
- 误报: 2 个（BUG-003、BUG-008）
- 部分误报/降级: 3 个（BUG-007、VULN-002、CONF-003）
- 待证实: 2 个（VULN-003、VULN-004）

---

## 二、真实BUG详细修复方案

### BUG-001 [严重] 数据库提交失败仍返回成功

#### 核验证据
**文件**: `app.py` 第 11556-11562 行
```python
try:
    db.session.commit()
except Exception as e:
    db.session.rollback()
    app.logger.error(f'数据库操作失败: {e}')
log_operation('新增BOM', f'BOM：{bom_no}', 'bom', bom.id)  # commit失败仍执行
return jsonify({'status': 'success', 'msg': 'BOM 新增成功'})  # 返回成功
```
**核验状态**: ✅ 确认存在。异常路径未 return，继续执行成功路径代码。

#### 修复方案
在 `except` 块中增加 `return` 错误响应：
```python
try:
    db.session.commit()
except Exception as e:
    db.session.rollback()
    app.logger.error(f'数据库操作失败: {e}')
    return jsonify({'status': 'error', 'msg': f'保存失败：{str(e)}'}), 500
log_operation('新增BOM', f'BOM：{bom_no}', 'bom', bom.id)
return jsonify({'status': 'success', 'msg': 'BOM 新增成功'})
```

#### 排查范围
全量搜索 `db.session.commit()` 共 219 处，重点排查模式：
```bash
# 搜索可疑模式：commit后有except但未return
grep -A 5 "except Exception" app.py | grep -B 2 "return.*success"
```

---

### BUG-002 [严重] 库存扣减缺少事务隔离

#### 核验证据
**文件**: `app.py` 第 3429-3437 行
```python
ok, msg = deduct_stock(material, quantity, 'out', 'out_order', order.id, ...)
if not ok:
    db.session.rollback()
    return api_json_error(msg)
location = (line.get('warehouse_code') or line.get('location_code') or order.warehouse or '').strip()
ok, msg = update_location_inventory(material, location, -quantity)
if not ok:
    db.session.rollback()  # 库存已扣但库位失败
    return api_json_error(msg)
```
**核验状态**: ✅ 确认存在。两步操作之间无行锁，并发下可能超卖。

#### 修复方案
1. **方案A（推荐）**: 使用 SELECT ... FOR UPDATE 锁定物料行
```python
material = db.session.query(Material).filter_by(id=material_id).with_for_update().first()
ok, msg = deduct_stock(material, quantity, ...)
if not ok:
    db.session.rollback()
    return api_json_error(msg)
ok, msg = update_location_inventory(material, location, -quantity)
if not ok:
    db.session.rollback()  # 整个事务回滚，库存扣减也撤销
    return api_json_error(msg)
```

2. **方案B**: 使用乐观锁版本号
```python
# Material模型增加version字段
material.stock -= quantity
material.version += 1
# UPDATE ... WHERE id=? AND version=?
```

3. **方案C**: 使用单个原子操作合并两步
```python
def deduct_stock_and_update_location(material, location, quantity, ...):
    # 单事务内完成，要么全成功要么全失败
```

---

### BUG-004 [中] 仓库/部门新增缺异常处理

#### 核验证据
**文件**: `app.py` 第 5216-5218 行
```python
db.session.add(warehouse)
db.session.commit()  # 无 try-except
return jsonify({'status': 'success', 'msg': '新增成功'})
```
**核验状态**: ✅ 确认存在。约束冲突会抛未捕获异常导致 500。

#### 修复方案
```python
try:
    db.session.add(warehouse)
    db.session.commit()
except Exception as e:
    db.session.rollback()
    app.logger.error(f'新增仓库失败: {e}')
    return jsonify({'status': 'error', 'msg': f'新增失败：{str(e)}'}), 500
return jsonify({'status': 'success', 'msg': '新增成功'})
```

#### 影响范围
- `add_warehouse()` - 第 5217 行
- `add_department()` - 第 5455 行
- 其他类似模式的路由需统一排查

---

### BUG-005 [中] 物料复制编码生成逻辑缺陷

#### 核验证据
**文件**: `app.py` 第 5031-5102 行
```python
# 硬编码假设编码6位
if len(source_code) < 6:
    # fallback到-COPY后缀
    base_code = f"{source_code}-COPY"
else:
    category_prefix = source_code[:3]
    serial_str = code[3:6]  # 假设后3位是流水号
    if new_serial > 999:
        raise ValueError(f"分类 {category_prefix} 的流水号已达上限(999)")
```
**核验状态**: ✅ 确认存在。编码格式硬编码，999上限可能不够。

#### 修复方案
1. **短期**: 增加 fallback 处理更多编码格式
2. **长期**: 重构编码生成策略
```python
def generate_material_copy_code(source_code):
    # 通用策略：提取数字后缀递增
    import re
    match = re.match(r'^(.*?)(\d+)$', source_code)
    if not match:
        return f"{source_code}-COPY"
    
    prefix, num_str = match.groups()
    max_num = num_str
    
    # 查询所有同前缀编码
    existing = Material.query.with_entities(Material.code).filter(
        Material.code.like(f'{prefix}%')
    ).all()
    
    for (code,) in existing:
        m = re.match(rf'^{re.escape(prefix)}(\d+)$', code)
        if m and int(m.group(1)) > int(max_num):
            max_num = m.group(1)
    
    # 保留原位数，不够则补0
    new_num = int(max_num) + 1
    return f"{prefix}{new_num:0{len(num_str)}d}"
```

---

### BUG-006 [中] 期初库存调整无并发锁

#### 核验证据
**文件**: `app.py` 第 4751-4786 行
```python
def _apply_opening_stock_balance(opening, material, new_quantity, ...):
    old_quantity = normalize_stock_quantity(opening.quantity or 0) if opening else 0
    quantity_delta = normalize_stock_quantity(new_quantity - old_quantity)
    # 无 with_for_update() 锁
    if abs(quantity_delta) > STOCK_COMPARE_EPSILON:
        material.stock = normalize_stock_quantity((material.stock or 0) + quantity_delta)
```
**核验状态**: ✅ 确认存在。先读后写无锁。

#### 修复方案
```python
def _apply_opening_stock_balance(opening, material, new_quantity, ...):
    # 加行锁
    material = db.session.query(Material).filter_by(id=material.id).with_for_update().first()
    
    old_quantity = normalize_stock_quantity(opening.quantity or 0) if opening else 0
    quantity_delta = normalize_stock_quantity(new_quantity - old_quantity)
    
    if abs(quantity_delta) > STOCK_COMPARE_EPSILON:
        material.stock = normalize_stock_quantity((material.stock or 0) + quantity_delta)
        # ... 其余逻辑不变
```

---

### BUG-009 [中] 事件监听器泄漏

#### 核验证据
**文件**: `app.js` 第 1219-1223 行
```javascript
document.addEventListener('click', function(event) {
    if (!columnPanel.contains(event.target) && !columnBtn.contains(event.target)) {
        columnPanel.classList.remove('show');
    }
});
```
**核验状态**: ✅ 确认存在。`setupDetailTable()` 每次调用都新增监听器。

#### 修复方案
```javascript
// 方案1: 使用命名函数 + removeEventListener
function setupDetailTable() {
    // 先移除旧监听器
    if (setupDetailTable._clickHandler) {
        document.removeEventListener('click', setupDetailTable._clickHandler);
    }
    
    setupDetailTable._clickHandler = function(event) {
        if (!columnPanel.contains(event.target) && !columnBtn.contains(event.target)) {
            columnPanel.classList.remove('show');
        }
    };
    document.addEventListener('click', setupDetailTable._clickHandler);
}

// 方案2: 使用 AbortController
function setupDetailTable() {
    if (setupDetailTable._abortController) {
        setupDetailTable._abortController.abort();
    }
    setupDetailTable._abortController = new AbortController();
    document.addEventListener('click', function(event) {
        // ...
    }, { signal: setupDetailTable._abortController.signal });
}
```

---

### BUG-010 [中] ExcelTable 事件监听器未清理

#### 核验证据
**文件**: `excel-table.js` 第 45-72 行
```javascript
setupEditableCells() {
    const cells = this.table.querySelectorAll('.editable-cell');
    cells.forEach(cell => {
        const newCell = cell.cloneNode(true);  // 克隆
        cell.parentNode.replaceChild(newCell, cell);  // 替换
        newCell.addEventListener('dblclick', ...);  // 旧节点的监听器泄漏
    });
}
```
**核验状态**: ✅ 确认存在。注释说"移除旧的事件监听器"但实际 cloneNode 不会移除原节点的监听器（替换后原节点失去引用，但事件监听器仍占内存直到 GC）。

#### 修复方案
```javascript
setupEditableCells() {
    const cells = this.table.querySelectorAll('.editable-cell');
    cells.forEach(cell => {
        // 使用 removeEventListener 显式移除
        if (cell._excelTableHandlers) {
            cell.removeEventListener('dblclick', cell._excelTableHandlers.dblclick);
            cell.removeEventListener('click', cell._excelTableHandlers.click);
            cell.removeEventListener('keydown', cell._excelTableHandlers.keydown);
        }
        
        const handlers = {
            dblclick: (e) => { e.stopPropagation(); this.startEdit(cell); },
            click: (e) => { e.stopPropagation(); this.selectCell(cell); },
            keydown: (e) => {
                if (!this.isEditing && this.isNumberKey(e.key)) {
                    this.startEdit(cell, e.key);
                    e.preventDefault();
                }
            }
        };
        cell._excelTableHandlers = handlers;
        cell.addEventListener('dblclick', handlers.dblclick);
        cell.addEventListener('click', handlers.click);
        cell.addEventListener('keydown', handlers.keydown);
    });
}
```

---

### BUG-011 [低] ExcelImportExport 重复创建模态框

#### 核验证据
**文件**: `excel-import-export.js` 第 97-147 行
```javascript
createImportModal() {
    const modalHtml = `<div class="modal fade" id="excelImportModal">...`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    // 未检查 #excelImportModal 是否已存在
}
```
**核验状态**: ✅ 确认存在。

#### 修复方案
```javascript
createImportModal() {
    // 检查是否已存在
    if (document.getElementById('excelImportModal')) {
        return;  // 已存在则不重复创建
    }
    
    const modalHtml = `...`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    // ... 绑定事件
}
```

---

### BUG-012 [低] 客户端导出跳过列逻辑错误

#### 核验证据
**文件**: `excel-import-export.js` 第 339-352 行
```javascript
cells.forEach((td, index) => {
    if (index === 0 || td.querySelector('input[type="checkbox"]') || td.querySelector('.btn')) {
        return;  // 基于 index 硬编码
    }
    if (headerIndex < headers.length) {
        rowData[headers[headerIndex]] = value;
        headerIndex++;
    }
});
```
**核验状态**: ✅ 确认存在。列顺序变化会错位。

#### 修复方案
```javascript
cells.forEach((td, index) => {
    // 基于 data-field 属性而非 index
    const field = td.dataset.field;
    if (!field) return;  // 跳过无字段的列（序号、操作等）
    
    let value = td.textContent.trim();
    value = value.replace(/¥|￥/g, '');
    
    // 根据 field 映射到表头
    const headerMap = {
        'material_code': '物料编码',
        'quantity': '数量',
        'price': '单价',
        // ...
    };
    const header = headerMap[field] || field;
    rowData[header] = value;
});
```

---

### VULN-001 [中] 打印模板HTML净化失败返回空

#### 核验证据
**文件**: `utils.py` 第 369-376 行
```python
def sanitize_print_html(html_content):
    if not html_content:
        return ''
    try:
        parser = _PrintHtmlSanitizer()
        parser.feed(html_content)
        parser.close()
        return parser.get_output()
    except Exception:
        return ''  # 用户看到空白打印页
```
**核验状态**: ✅ 确认存在。已有白名单净化防御，但失败时静默返回空。

#### 修复方案
```python
def sanitize_print_html(html_content):
    if not html_content:
        return ''
    try:
        parser = _PrintHtmlSanitizer()
        parser.feed(html_content)
        parser.close()
        return parser.get_output()
    except Exception as e:
        app.logger.error(f'打印模板HTML净化失败: {e}')
        # 返回错误提示而非空白
        return f'<div style="color:red;padding:20px;">打印模板渲染失败，请联系管理员</div>'
```

---

### CONF-001 [严重] SECRET_KEY 未强制配置

#### 核验证据
**文件**: `config.py` 第 34 行
```python
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')  # 可能为 None
```
**核验状态**: ✅ 确认存在。Flask 在 SECRET_KEY=None 时会用不安全默认值。

#### 修复方案
```python
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    def __init__(self):
        if not self.SECRET_KEY:
            raise RuntimeError(
                'SECRET_KEY 未配置！请设置环境变量 SECRET_KEY。\n'
                '生成方法: python -c "import secrets; print(secrets.token_hex(32))"'
            )

# 或者在 app.py 启动时检查
def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config_dict[config_name])
    
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('SECRET_KEY 未配置，拒绝启动')
    # ...
```

---

### CONF-002 [中] 开发配置泄露风险

#### 核验证据
**文件**: `config.py` 第 107-111 行
```python
class DevelopmentConfig(Config):
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get('DEV_SECRET_KEY')
    DEBUG = True
    SQLALCHEMY_ECHO = True
```
**核验状态**: ✅ 确认存在。开发配置若误用于生产会泄露信息。

#### 修复方案
```python
class DevelopmentConfig(Config):
    # 开发环境也要强制配置 SECRET_KEY
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get('DEV_SECRET_KEY')
    
    def __init__(self):
        if not self.SECRET_KEY:
            # 开发环境使用固定密钥并警告
            import warnings
            warnings.warn('DEV_SECRET_KEY 未配置，使用临时开发密钥')
            self.SECRET_KEY = 'dev-only-unsafe-secret-key-change-me'
    
    DEBUG = True
    SQLALCHEMY_ECHO = os.environ.get('SQL_ECHO', 'false').lower() == 'true'  # 默认关闭
```

---

### CONF-004 [中] SQLite 并发限制

#### 核验证据
**文件**: `config.py` 第 38 行
```python
SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "instance", "inventory.db")}'
```
**核验状态**: ✅ 确认存在。SQLite 写入串行化不适合高并发。

#### 修复方案
1. **短期**: 增加 WAL 模式提升并发
```python
from sqlalchemy import event

@event.listens_for(db.engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
```

2. **长期**: 迁移到 PostgreSQL 或 MySQL
```python
# config.py
class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://user:pass@localhost/wms'
    )
```

---

## 三、误报说明

### BUG-003 [原报告: 高] 委外收货数量双倍计算

#### 核验结果: ❌ 误报
**文件**: `app.py` 第 4095-4102 行
```python
# 注意：上面 db.session.add(receive_item) 后，SQLAlchemy 默认 autoflush 会在下次查询前
# 把 receive_item 刷入数据库，因此下面的 sum 查询已包含本次 quantity，不能再 + quantity，
# 否则 received_qty 会被双倍计算，可能把未完成订单误判为 completed
order_items = SubcontractItem.query.filter_by(subcontract_order_id=order_id).all()
total_qty = sum(item.quantity for item in order_items)
received_qty = sum(item.quantity for item in
                  SubcontractReceiveItem.query.join(SubcontractReceive)
                  .filter(SubcontractReceive.subcontract_order_id == order_id).all())
```
**说明**: 代码注释明确说明作者已意识到 autoflush 问题，sum 查询**没有**额外加 quantity，因此不会双倍计算。原报告误读了代码。

---

### BUG-008 [原报告: 高] 全局 confirmResolver 竞态条件

#### 核验结果: ❌ 误报
**文件**: `app.js` 第 1-69 行
```javascript
// 全局确认框队列
let confirmResolver = null;
let confirmQueue = [];        // 已改为队列
let activeConfirm = null;

function confirmDialog(message, options) {
    // ...
    return new Promise(function(resolve) {
        confirmQueue.push({        // 入队而非覆盖
            message: message,
            options: options,
            resolve: resolve
        });
        showNextConfirm();         // 依次处理
    });
}
```
**说明**: 代码已重构为队列实现，多个确认框会排队依次显示，不再有竞态条件。

---

### BUG-007 [原报告: 中] 部分误报

#### 核验结果: ⚠️ 实为死代码而非逻辑矛盾
**文件**: `app.py` 第 5900-5945 行
```python
# 第1步: 有引用则 continue
if (InOrderItem.query.filter_by(material_id=id).first() or ...):
    fail_count += 1
    continue  # 跳过

# 第2步: 删除关联（实际不会执行，因第1步已continue）
InOrderItem.query.filter_by(material_id=id).delete()
```
**说明**: 第1步检查到有引用会 continue，所以第2步的 delete 对这些物料永远不会执行。这是**冗余死代码**，不是逻辑矛盾。但对无引用的物料，第2步删除0条记录是安全的。

---

### VULN-002 [原报告: 高] 部分误报

#### 核验结果: ⚠️ 已有 sanitize 保护
**文件**: `print_out_with_html.html` 第 63 行
```html
{{ rendered_content|safe }}
```
**说明**: 虽然使用了 |safe，但 `rendered_content` 来自 `sanitize_print_html()` 净化后的输出，已过滤 script/on*/javascript: 等危险内容。实际风险为**低**，仅在管理员账号被攻破后才有理论风险。

---

### CONF-003 [原报告: 中] 部分误报

#### 核验结果: ⚠️ 生产配置已修正
**文件**: `config.py` 第 119 行
```python
class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1', 'yes')
```
**说明**: 基础 Config 类确实是 False，但 ProductionConfig 已支持通过环境变量启用。只要生产环境设置 `SESSION_COOKIE_SECURE=true` 即可。风险降为**低**。

---

## 四、修复优先级排序

### P0 - 立即修复（严重）
1. **BUG-001**: commit 失败仍返回 success - 影响所有核心业务
2. **BUG-002**: 库存扣减无事务隔离 - 并发超卖风险
3. **CONF-001**: SECRET_KEY 未强制配置 - 会话安全

### P1 - 近期修复（高/中）
4. **BUG-006**: 期初库存调整无并发锁
5. **BUG-004**: 仓库/部门新增缺异常处理
6. **VULN-001**: 打印模板净化失败返回空
7. **BUG-009**: 事件监听器泄漏
8. **BUG-010**: ExcelTable 监听器未清理

### P2 - 计划修复（中/低）
9. **BUG-005**: 物料复制编码生成缺陷
10. **CONF-002**: 开发配置泄露风险
11. **CONF-004**: SQLite 并发限制
12. **BUG-011**: ExcelImportExport 重复模态框
13. **BUG-012**: 客户端导出列错位
14. **BUG-007**: 死代码清理

### P3 - 观察验证
- VULN-003: CSRF Token 覆盖率 - 需全量审计表单
- VULN-004: 密码策略一致性 - 需审计所有改密路径

---

## 五、修复实施建议

### 5.1 统一事务管理模式

建议创建装饰器统一处理事务：
```python
def transactional_route(success_msg='操作成功', error_msg='操作失败'):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
                db.session.commit()
                return result
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'{f.__name__} 失败: {e}')
                return jsonify({'status': 'error', 'msg': f'{error_msg}: {str(e)}'}), 500
        return wrapper
    return decorator
```

### 5.2 统一库存操作接口

```python
@transactional
def deduct_stock_with_location(material_id, location, quantity, ref_type, ref_id, remark):
    """原子化库存扣减 + 库位更新"""
    material = Material.query.with_for_update().filter_by(id=material_id).first()
    if not material or material.stock < quantity:
        raise ValueError('库存不足')
    
    material.stock -= quantity
    # 更新库位库存
    loc_inv = LocationInventory.query.with_for_update().filter_by(
        material_id=material_id, location=location
    ).first()
    if loc_inv:
        loc_inv.quantity -= quantity
    
    db.session.add(StockTransaction(...))
```

### 5.3 前端事件管理规范

```javascript
// 创建事件管理基类
class EventManager {
    constructor() {
        this._listeners = [];
    }
    
    track(target, event, handler, options) {
        target.addEventListener(event, handler, options);
        this._listeners.push({ target, event, handler, options });
    }
    
    cleanup() {
        this._listeners.forEach(({ target, event, handler, options }) => {
            target.removeEventListener(event, handler, options);
        });
        this._listeners = [];
    }
}
```

### 5.4 配置启动校验

```python
def validate_config(app):
    """启动时校验关键配置"""
    errors = []
    
    if not app.config.get('SECRET_KEY'):
        errors.append('SECRET_KEY 未配置')
    
    if app.config.get('DEBUG') and app.env == 'production':
        errors.append('生产环境不能开启 DEBUG')
    
    if errors:
        raise RuntimeError('配置校验失败:\n' + '\n'.join(errors))
```

---

## 六、测试验证建议

### 6.1 事务管理测试
```python
def test_commit_failure_returns_error():
    """BUG-001 回归测试"""
    with patch.object(db.session, 'commit', side_effect=Exception('DB error')):
        response = client.post('/api/bom/add', json={...})
        assert response.json['status'] == 'error'
        assert response.status_code == 500
```

### 6.2 并发库存测试
```python
def test_concurrent_stock_deduction():
    """BUG-002 回归测试"""
    material = Material.query.first()
    initial_stock = material.stock
    
    threads = [
        threading.Thread(target=lambda: client.post('/api/out/submit', json={
            'material_id': material.id,
            'quantity': initial_stock / 2  # 两个线程各扣一半
        })),
        threading.Thread(target=lambda: client.post('/api/out/submit', json={
            'material_id': material.id,
            'quantity': initial_stock / 2
        }))
    ]
    
    for t in threads: t.start()
    for t in threads: t.join()
    
    material = Material.query.first()
    assert material.stock == 0  # 应该正好扣完，不应超卖
```

### 6.3 前端内存泄漏测试
```javascript
// BUG-009/010 回归测试
function testEventListenerLeak() {
    const initialCount = getEventListeners(document).click.length;
    setupDetailTable();  // 调用多次
    setupDetailTable();
    setupDetailTable();
    const finalCount = getEventListeners(document).click.length;
    assert.equal(finalCount, initialCount + 1, '不应累积监听器');
}
```

---

## 七、总结

### 核验结论
- 原报告 20 个 BUG 中，**15 个真实存在**，**2 个误报**，**3 个部分误报/降级**
- 真实存在的严重问题集中在**事务管理**和**配置安全**
- 前端问题主要是**内存泄漏**，影响长时间使用

### 修复工作量评估
- P0 严重问题: 3 个，需立即处理
- P1 高优先级: 5 个，建议近期修复
- P2 中低优先级: 6 个，可计划修复
- P3 待验证: 2 个，需进一步审计

### 风险提示
1. **BUG-001 和 BUG-002 是最高风险**，可能导致数据丢失和超卖
2. **CONF-001 是安全隐患**，攻击者可伪造会话
3. 修复时需注意回归测试，避免引入新问题

---

**报告生成时间**: 2026-06-27
**核验方式**: 逐条读取源代码验证
**代码修改**: 无（仅分析报告）
