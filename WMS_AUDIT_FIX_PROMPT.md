# AI 修复 WMS 基础资料缺陷 — 提示词

> 用途：把 `/workspace/wms_audit_20260727_120000.md` 列出的 4 个致命、5 个一般、5 个提示缺陷**按优先级一次性修完**，并由 AI 自行 commit + push。
> 工作目录：`/workspace`
> 目标分支：`main`（**禁止**创建 feature/fix/chore/trae/* 等任何新分支；本地 `.githooks/pre-push` 与 AGENTS.md 已硬约束）

---

## 0. 必须遵守的硬规则

1. **工作分支：仅 `main`**。禁止 `git checkout -b`、禁止 `gh repo create`、禁止 `git push origin HEAD:xxx`。
2. **禁止自动改/重置/生成任何用户密码**，包括 admin bootstrap。修改前必须取得用户显式授权。
3. **已完成入库单禁止硬删**。所有入库/出库/盘点等已完成单据的 `delete_*` 路由必须先反提交到草稿并回退库存，再允许删除。
4. **每完成一个任务必须**：
   - 跑相关验证脚本（如 `scripts/verify_high_priority_fixes.py`、`verify_ai_business_permissions.py`）拿到 exit 0 输出；
   - `git add <具体文件>`（不要 `git add -A` / `git add .`）；
   - `git commit -m "fix(<scope>): <一句话说明>"`；
   - `git push origin main`；
   - 把 commit SHA 写进 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 对应 task 行。
5. **不要把 secrets/.env/credentials.json 加入 commit**。
6. **不要重新开发已完成 capability**。改前先查 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 任务 ID 是否已 `DONE`；若是，使用 child fix ID（如 `AI-F-01-fix1`）。

---

## 1. 任务清单（按 P0 → P2 顺序）

### P0-F-01：员工删除加业务引用校验
- 文件：`app/app.py`（约 23884 行的 `delete_employee`）
- 改动：
  ```python
  # 在 db.session.delete(emp) 之前，先查所有 operator_id 引用
  from sqlalchemy import or_
  blockers = []
  for Model, col in [
      (InOrder, 'operator_id'),
      (OutOrder, 'operator_id'),
      (PurchaseOrder, 'operator_id'),
      (SalesOrder, 'operator_id'),
      (Check, 'operator_id'),
      (Transfer, 'operator_id'),
      (Adjustment, 'operator_id'),
      (AfterSaleOut, 'operator_id'),
  ]:
      if hasattr(Model, col):
          n = Model.query.filter(getattr(Model, col) == emp.id).count()
          if n:
              blockers.append(f"{Model.__name__}.{col} 引用 {n} 次")
  if blockers:
      return jsonify(success=False, error="员工已被业务单据引用，禁止删除：\n" + "\n".join(blockers)), 409
  ```
- 验证：构造一个被 InOrder.operator_id 引用的员工，POST `/employee/delete`，必须返回 409 + 中文错误。

### P0-F-02：分类删除加 Material 引用校验
- 文件：`app/app.py`（约 8902 行的 `delete_category`）
- 改动：
  ```python
  mat_n = Material.query.filter_by(category_id=cat.id).count()
  if mat_n:
      return jsonify(success=False, error=f"分类已被 {mat_n} 个物料引用，禁止删除"), 409
  ```
- 验证：构造一个被 5 个物料引用的分类，POST `/category/delete`，必须返回 409。

### P0-F-03：合同/工程加导入路由
- 文件：`app/app.py`（新增）+ `app/templates/contract.html`（顶部工具栏加导入按钮）
- 改动：
  1. `app/app.py` 新增：
     ```python
     @app.route('/contract/import', methods=['POST'])
     @login_required
     @require_role('admin')
     def import_contract():
         f = request.files.get('file')
         if not f or not validate_excel_extension(f.filename):
             return jsonify(success=False, error='仅支持 .xlsx/.xls'), 400
         try:
             wb = load_workbook(filename=BytesIO(f.read()), data_only=True)
             ws = wb.active
           rows = list(ws.iter_rows(values_only=True))
             header = [str(c).strip() if c else '' for c in rows[0]]
             required = ['合同号', '合同名称', '供应商', '签订日期', '金额']
             missing = [c for c in required if c not in header]
             if missing:
                 return jsonify(success=False, error=f'缺少列: {missing}'), 400
             ok = 0
             for r in rows[1:]:
                 if not r or not r[0]: continue
                 d = dict(zip(header, r))
                 c = Contract.query.filter_by(contract_no=str(d['合同号']).strip()).first()
                 if c:
                     c.contract_name = d.get('合同名称') or c.contract_name
                     # ...其他字段更新
                 else:
                     db.session.add(Contract(contract_no=str(d['合同号']).strip(), ...))
                 ok += 1
             db.session.commit()
             return jsonify(success=True, message=f'导入 {ok} 条'))
         except Exception as e:
             db.session.rollback()
             return jsonify(success=False, error=str(e)), 500
     ```
  2. `contract.html` `page-header` 加按钮：`<button class="btn btn-outline-primary btn-sm" data-bs-toggle="modal" data-bs-target="#importModal"><i class="bi bi-upload"></i> 导入</button>`
  3. 加 `#importModal`（参照 `material.html:754-777` 的弹窗结构）。
- 验证：上传 3 行合同 Excel → 数据库新增 3 条 → 二次上传同合同号 → 不重复新增（更新）。

### P0-F-04：batch_import.html 增 3 张卡片
- 文件：`app/templates/batch_import.html`（在现有 8 张卡片末尾追加）
- 改动（参考现有卡片结构，**3 张**）：
  ```html
  <!-- 仓库 -->
  <div class="col-md-6"><div class="card">
    <div class="card-header"><h5 class="mb-0">导入仓库</h5></div>
    <div class="card-body">
      <p class="text-muted small">表头需含：仓库编号、仓库名称、类型、地点、状态</p>
      <form class="import-form" data-url="/warehouse/import" enctype="multipart/form-data">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="file" class="form-control mb-2" name="file" accept=".xlsx,.xls" required>
        <button class="btn btn-primary btn-sm" type="submit"><i class="bi bi-upload"></i> 导入仓库</button>
        <a href="/warehouse/download_template" class="btn btn-sm btn-outline-secondary ms-2"><i class="bi bi-download"></i> 下载模板</a>
      </form>
      <div class="import-result mt-2"></div>
    </div></div></div>
  <!-- 部门 -->
  <div class="col-md-6"><div class="card">
    <div class="card-header"><h5 class="mb-0">导入部门</h5></div>
    <div class="card-body">
      <p class="text-muted small">表头需含：部门编号、部门名称、上级部门</p>
      <form class="import-form" data-url="/department/import" enctype="multipart/form-data">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="file" class="form-control mb-2" name="file" accept=".xlsx,.xls" required>
        <button class="btn btn-primary btn-sm" type="submit"><i class="bi bi-upload"></i> 导入部门</button>
        <a href="/department/download_template" class="btn btn-sm btn-outline-secondary ms-2"><i class="bi bi-download"></i> 下载模板</a>
      </form>
      <div class="import-result mt-2"></div>
    </div></div></div>
  <!-- 客户 -->
  <div class="col-md-6"><div class="card">
    <div class="card-header"><h5 class="mb-0">导入客户</h5></div>
    <div class="card-body">
      <p class="text-muted small">表头需含：客户编号、客户名称、联系人、电话、地址</p>
      <form class="import-form" data-url="/customer/import" enctype="multipart/form-data">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="file" class="form-control mb-2" name="file" accept=".xlsx,.xls" required>
        <button class="btn btn-primary btn-sm" type="submit"><i class="bi bi-upload"></i> 导入客户</button>
        <a href="/customer/download_template" class="btn btn-sm btn-outline-secondary ms-2"><i class="bi bi-download"></i> 下载模板</a>
      </form>
      <div class="import-result mt-2"></div>
    </div></div></div>
  ```
- 验证：浏览器访问 `/batch_import`，确认共 11 张卡片；任选一卡片 → 下载模板 → 填 1 行 → 上传 → 列表显示新数据。

### P1-M-01：5 个基础资料加 editXxx 函数 + 行级编辑按钮
- 文件：`app/templates/{unit,supplier,customer,employee,category}.html` + `app/app.py` 新增 `edit_<resource>` 路由
- 改动：每个页面行操作列在删除前加 `<button class="btn btn-sm btn-outline-primary me-1" onclick="editXxx(<id>)">编辑</button>`，并在页面底部加 `function editXxx(id){...fetch + 弹窗}` 完整实现（参照 `material.html` 的 edit 流程）。后端新增 `edit_unit/supplier/customer/employee/category` 5 个 PUT 路由。
- 验证：进入任一模块 → 行级点编辑 → 弹窗显示原值 → 改名 → 保存 → 列表更新。

### P1-M-02：8 个基础资料页加顶部工具栏
- 文件：`app/templates/{category,unit,supplier,customer,employee,warehouse,department,contract}.html`
- 改动：在 `page-header` 区域统一加 4 按钮（新增 / 导入 / 导出 / 下载模板），按钮 trigger 对应模态（warehouse.html / department.html 缺模态，需先补 `#addModal` / `#importModal`）。`contract.html` 补「新增」+「导入」。
- 验证：进入每个基础资料页 → 顶部 4 按钮可见且能点开对应模态或跳转对应下载。

### P1-M-03：Warehouse 加 is_default 字段 + 设为默认按钮
- 文件：`app/models.py`（Warehouse 模型）+ `app/app.py`（迁移 + 切换接口）+ `app/templates/warehouse.html`（行级按钮）
- 改动：
  ```python
  class Warehouse(db.Model):
      # ... 现有字段 ...
      is_default = db.Column(db.Boolean, default=False, nullable=False)
  ```
  新增路由 `POST /warehouse/<id>/set_default`：先把所有 `is_default=True` 置 False，再把当前行置 True（同一事务）。行级加 `<button onclick="setDefault(<id>)">设为默认</button>`。
- 验证：建 3 个仓库 → 把 #2 设为默认 → 列表中 #2 显示「默认」徽标，其他两行徽标消失。

### P1-M-04：Employee 加 code + department_id 字段
- 文件：`app/models.py`（Employee 模型）+ 一次性迁移
- 改动：
  ```python
  class Employee(db.Model):
      # ... 现有字段 ...
      code = db.Column(db.String(64), unique=True, nullable=True)  # nullable=True 兼容老数据
      department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
      department = db.relationship('Department', backref='employees', lazy='joined')
  ```
  一次性数据迁移脚本：`UPDATE employee SET code = 'EMP' || id WHERE code IS NULL;`
- 验证：`SELECT code, department_id FROM employee LIMIT 5;` 不再全为 NULL；建员工时传 code/department_id → 保存成功。

### P2-M-05：合同删除增 InOrderDetail.contract_no 字符串匹配
- 文件：`app/app.py`（约 8115 行的 `_contract_delete_blockers`）
- 改动：
  ```python
  n = db.session.query(InOrderDetail).join(InOrder, InOrderDetail.in_order_id == InOrder.id)\
        .filter(InOrderDetail.contract_no == contract.contract_no).count()
  if n:
      blockers.append(f"InOrderDetail.contract_no 引用 {n} 次")
  # 同样补 OutOrderDetail / PurchaseOrderDetail / SalesOrderDetail
  ```
- 验证：建一个合同号 C001 → 入库单明细行 contract_no=C001 → 删合同 C001 → 期望 409。

### P2-m-01：客户删除增 OtherInOrderDetail.customer_id FK 校验
- 文件：`app/app.py`（约 23751 行的 `delete_customer`）
- 改动：`n = OtherInOrderDetail.query.filter_by(customer_id=customer.id).count(); if n: return 409`
- 验证：构造 OtherInOrderDetail.customer_id = C → 删客户 C → 期望 409。

### P2-m-03：全局限制 Excel 上传 ≤ 5MB
- 文件：`app/app.py`
- 改动：`app.config.setdefault('MAX_CONTENT_LENGTH', 5 * 1024 * 1024)`（在 `app = Flask(__name__)` 之后一行）。
- 验证：上传 6MB xlsx → 期望 413 Request Entity Too Large。

---

## 2. 执行步骤（AI 严格按此顺序）

```bash
# 0. 准备
cd /workspace
git status
git log -n 3 --oneline

# 1. 拉一个干净的 main（不要建分支）
git checkout main
git pull --rebase origin main

# 2. 修 P0 四个 → 每个改完立即验证 + commit + push
#    每个 P0 任务对应一次 commit
#    例：fix(emp-delete): F-01 add operator_id reference checks

# 3. 跑一遍综合验证
python scripts/verify_high_priority_fixes.py        # 期望 exit 0
python scripts/verify_medium_low_fixes.py           # 期望 exit 0
python scripts/verify_ai_business_permissions.py    # 期望 exit 0

# 4. 更新 WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md
#    对每个修完的 task 行追加：
#    DONE 2026-07-27  commit=<sha>  modules=<files>  validate=<cmd>  result=pass

# 5. 最终汇总
git log -n 14 --oneline
git push origin main
```

---

## 3. 验收清单（AI 修完必须勾完）

- [ ] P0-F-01 employee.delete 引用校验生效
- [ ] P0-F-02 category.delete 物料引用校验生效
- [ ] P0-F-03 contract.import 路由存在且 contract.html 工具栏有「导入」按钮
- [ ] P0-F-04 /batch_import 渲染 11 张卡片，仓库/部门/客户可正常导入
- [ ] P1-M-01 5 模块行级 edit 按钮 + editXxx 函数 + 后端 PUT 路由 全部就绪
- [ ] P1-M-02 8 基础资料页顶部 4 按钮齐全
- [ ] P1-M-03 Warehouse.is_default 字段 + 切换接口 + 行级徽标 全部就绪
- [ ] P1-M-04 Employee.code + department_id 字段 + 一次性数据迁移脚本就绪
- [ ] P2-M-05 合同删除阻断 InOrderDetail.contract_no 引用
- [ ] P2-m-01 客户删除阻断 OtherInOrderDetail.customer_id 引用
- [ ] P2-m-03 MAX_CONTENT_LENGTH=5MB 生效
- [ ] 全部 commit 已 push 到 `main`（**未**新建任何分支）
- [ ] WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md 任务状态已更新
- [ ] 验证脚本全部 exit 0，输出已贴到 ledger

---

## 4. 失败回退

任一 P0 任务验证未通过：
1. `git revert <sha>` 回退该 commit
2. 在 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 该 task 行加 `BLOCKED: <原因>`
3. 继续修其他独立 P0，最后再回头修这一个
4. **不要**因为一个 P0 失败就跳过其他 P0

---

## 5. 关键文件路径速查

| 用途 | 路径 |
|---|---|
| 报告 md | `wms_audit_20260727_120000.md` |
| 报告 json | `wms_audit_20260727_120000.json` |
| 主程序 | `app/app.py` |
| 模型 | `app/models.py` |
| 集中导入页 | `app/templates/batch_import.html` |
| 物料导入参考模板 | `app/templates/material.html:754-777` |
| 通用导入前端组件 | `app/static/js/excel-import-export.js` |
| AI 任务台账 | `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` |
| 高优先级验证 | `scripts/verify_high_priority_fixes.py` |
| 中低优先级验证 | `scripts/verify_medium_low_fixes.py` |
| 权限矩阵验证 | `scripts/verify_ai_business_permissions.py` |
| 预推送钩子 | `.githooks/pre-push`（禁止 push 非 main 分支） |
