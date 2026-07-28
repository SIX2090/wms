# MASTER-AUDIT-FIX-2026-07-28-F02 — 详细修复提示词

## 上下文

- 主仓库：`https://github.com/SIX2090/wms.git`（**唯一工作分支 main**）
- 上一阶段：`MASTER-AUDIT-FIX-2026-07-28-F01`（1 P0 + 14 P1，已完成）
- 本阶段：`MASTER-AUDIT-FIX-2026-07-28-F02`（**8 项 UX/质量缺陷**）
- 工作目录：`c:\Users\Administrator\Desktop\wms`
- 启动器：`python audit_screenshots/start_server.py`（已重构为真分离子进程）
- 验收基线：WMS_BUG_BASELINE.md（已有 20 条 2026-07-28 修复记录）
- 任务台账：WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md（追加 F02 完成记录）

## 8 项修复清单（每项独立 commit + 独立验证）

### BUG-F02-01（P2）基础资料排序：物料/客户/供应商/仓库/部门 列表默认按 `code` 升序，但用户偏好不明 + 排序字段没有"中文 label + 视觉箭头"

**现状**：
- `app/app.py:7037 material_list` / `24002 supplier_list` / `24139 customer_list` / `7809 warehouse_list` / `9127 category_list` 等均使用 `_get_master_list_filters` + `_apply_master_order`，但默认 `sort_by='created_at'`、`sort_order='desc'`，用户进列表页看到的几乎都是"最新创建在前"
- `app/templates/_list_macros.html` 已实现 `sort_th()` 宏，但部分模板（如 `material.html` / `supplier.html` / `customer.html` / `warehouse.html`）的"创建时间"列没有用 `sort_th` 而是普通 `<th>`

**修复方案**：
1. `app/app.py` 5 个 list 函数默认 `sort_by='code'`、`sort_order='asc'`（与人类查字典习惯一致）
2. 检查并补全 5 个 list 模板中所有可排序列的 `sort_th()` 宏替换
3. `custom.css` 加 `.sort-th-active` 样式让激活列更醒目

**验收点**：
- 进 `/material` 第一行应是 `code` 最小的物料
- 点列头切换 asc/desc，箭头跟随
- `audit_screenshots/verify_f02_01_sort.py`：5 列表 × 3 检查 = 15 项全绿

### BUG-F02-02（P1）物料 API 截断：物料编码/名称/规格/品牌/用途/备注超长时被 DB 静默截断

**现状**：
- `app/app.py:7142 add_material` 仅校验 `brand > 100`，未校验 `code`（DB 限 50）、`name`（DB 限 100）、`spec`（DB 限 100）、`purpose`（DB 限 200）、`remark`（DB 限 500）
- 同样问题在 `edit_material` / 批量导入 / 客户 / 供应商 增改都可能存在
- 用户提交 60 字符 code，DB 写入 50 字符，前端查询显示尾巴没了，但 `msg: '物料新增成功'`

**修复方案**：
1. `app/app.py:7142 add_material` 入口加：
   ```python
   if len(code) > 50: return jsonify({'status':'error','msg':'物料编码不能超过 50 个字符（当前 '+str(len(code))+'）'}), 400
   if len(name) > 100: return ... '100'
   if len(spec) > 100: return ... '100'
   if len(purpose) > 200: return ... '200'
   if len(remark) > 500: return ... '500'
   ```
2. `app/app.py:8752 edit_material` 同样 5 个长度校验
3. `app/app.py:add_supplier` / `edit_supplier` / `add_customer` / `edit_customer` 同步加（code 50 / name 100 / contact 50 / phone 30 / address 200 / remark 500）
4. `audit_screenshots/verify_f02_02_truncate.py`：11 个字段 × 边界值（超 1 字符 / 临界 1 字符 / 正常 1 字符）= 33 项全绿

**验收点**：
- 提交 51 字符 code → `400` + 中文 msg
- 提交 50 字符 code → `200` 成功
- `add_material` / `edit_material` / `add_supplier` / `edit_supplier` / `add_customer` / `edit_customer` 6 路由全部覆盖

### BUG-F02-03（P0）标签模板静默覆盖：保存布局失败但 JS 误报成功

**现状**：
- `app/templates/label_template_detail.html:675 saveLayout()` 调用 `fetch('/label_template/{{ template.id }}/save_layout', ...)`
- **该路由在 `app/app.py` 中不存在**（grep `save_layout` 0 hit）
- 用户拖完字段点"保存布局"→ 后端 404/405 → 前端 `data.status` 是 undefined → `data.status === 'success'` 假阳性 → `alert('布局保存成功！')` 误导
- 实际数据没保存，下次进页面布局丢失

**修复方案**：
1. `app/app.py` 新增 `save_label_template_layout(id)` 路由（`methods=['POST']`、`@login_required`、`@require_role('admin','warehouse')`）：
   ```python
   @app.route('/label_template/<int:id>/save_layout', methods=['POST'])
   @require_role('admin', 'warehouse')
   @login_required
   def save_label_template_layout(id):
       template = LabelTemplate.query.get_or_404(id)
       data = request.get_json(silent=True) or {}
       layout = data.get('layout')
       if not layout:
           return jsonify({'status':'error','msg':'布局数据不能为空'}), 400
       template.layout = json.dumps(layout, ensure_ascii=False)
       template.updated_at = datetime.now()
       try:
           db.session.commit()
       except Exception as exc:
           db.session.rollback()
           return jsonify({'status':'error','msg':'保存失败'}), 500
       log_operation('更新标签模板布局', f'template_id={id}, name={template.name}', 'label_template', id)
       return jsonify({'status':'success','msg':'布局已保存'})
   ```
2. `label_template_detail.html:saveLayout()` JS 增强：
   - 加 `response.ok` 检查（`fetch` 本身 404 不会走 `data.status === 'success'`，但保险起见加）
   - 加"保存中..."disabled 态防止双击
   - 失败时 `console.error` 输出响应体
3. `audit_screenshots/verify_f02_03_label_save.py`：登录 → POST 空 layout → 400；POST 正常 layout → 200 + 二次进入 GET 详情页布局回显

**验收点**：
- `fetch` 返回 200 + `{"status":"success","msg":"布局已保存"}`
- `LabelTemplate.layout` 列写入新 JSON
- 二次进入页面拖动位置保留
- 权限：无 admin/warehouse 角色 → 403

### BUG-F02-04（P1）库位主数据/库存归属：Location 列表状态变更不联动库存

**现状**：
- `app/app.py` 有 `Location` 类（库位）和 `LocationInventory` 类（库位库存）
- 但 `Location` 是否启用状态字段未确认，需要 grep
- `LocationInventory.location` 仅是字符串，**没有外键约束**，如果 Location 改名/禁用/删除，`LocationInventory` 数据不联动

**修复方案**（先确认现状再修）：
1. grep `class Location` 看 Location 是否有 `is_active`/`status` 字段
2. 如果有 `is_active`，加 Location 列表页 `/location`（已存在则增强）：展示"该库位下有多少库存"列
3. `LocationInventory` 增 `?` 面板：盘点/调整/调拨单选择库位时下拉只显示 `is_active=True` 且库存 > 0 的项
4. **库位归属不明时不自动猜**：盘点时如果选了不存在的库位 code，后端返回 400 + 提示"库位 X 不存在或已停用，请联系管理员"

**验收点**：
- `audit_screenshots/verify_f02_04_location.py`：停用某库位 → 单据选下拉已无该项 → 库存数据保留不删除

### BUG-F02-05（P2）关闭库位管理后业务可用性：location_management_enabled=False 时入/出库/调拨/盘点/调整仍要求选库位

**现状**：
- `app/app.py:5274` 在 in_order 处理逻辑中检查 `if location_management_enabled() and location_required_on_save():` → 关闭后库位校验被跳过
- 但前端 `/in_order/add` 模板可能仍把"库位"字段渲染为必填 `<select required>`

**修复方案**：
1. grep `app/templates/in_order_add.html` `out_order_add.html` `transfer_add.html` `check_add.html` `adjustment_add.html` 中库位字段
2. 对 5 个新增模板加 `{% if location_management_enabled() %}` 包裹库位字段（标签 + select + required 标志）
3. `custom.css` 加 `.field-hidden { display: none !important; }` 作为兜底
4. `audit_screenshots/verify_f02_05_location_off.py`：登录 admin → POST `/system_settings` 设置 `location_management_enabled=0` → 验证 5 个新增页 HTML 中库位字段不存在 → 提交入库单不报"库位必填"

**验收点**：
- 关闭后 5 个新增页库位 `<select>` 不渲染
- 提交入库单成功
- 开启后 5 个新增页库位 `<select>` 重新渲染

### BUG-F02-06（P1）用户资料编辑：admin 改自己/普通用户改自己的资料没有审计 last_modified_by/前后对比

**现状**：
- `app/app.py:6741 edit_user` admin 改任意用户**有**审计（`log_operation('编辑用户', before -> after)`）
- 但普通用户改自己**没有**专用接口 — 当前 `/user/<id>/edit` 路由是 `require_role('admin')`
- 用户想改自己电话/邮箱没有入口
- 即使 admin 改，审计日志里没有 `last_modified_by`（虽然 `current_user` 可推断）

**修复方案**：
1. `app/app.py` 新增 `edit_my_profile`（`@login_required`、无 role_required、仅改自己）：
   ```python
   @app.route('/profile/edit', methods=['POST'])
   @login_required
   def edit_my_profile():
       user = current_user
       # 仅允许改：邮箱、电话、备注；不可改：用户名/角色/状态/密码
       email = (request.form.get('email') or '').strip()[:200]
       phone = (request.form.get('phone') or '').strip()[:30]
       bio = (request.form.get('bio') or '').strip()[:500]
       if email and '@' not in email:
           return jsonify({'status':'error','msg':'邮箱格式不正确'}), 400
       if not re.fullmatch(r'^[\d\-\+\s]{0,30}$', phone):
           return jsonify({'status':'error','msg':'电话只能包含数字/-/+/空格'}), 400
       before = f'email={user.email}, phone={user.phone}, bio={user.bio}'
       user.email = email or user.email
       user.phone = phone or user.phone
       user.bio = bio or user.bio
       try:
           db.session.commit()
       except Exception:
           db.session.rollback()
           return jsonify({'status':'error','msg':'保存失败'}), 500
       log_operation('编辑自己的资料', f'{before} -> email={user.email}, phone={user.phone}, bio={user.bio}', 'user', user.id)
       return jsonify({'status':'success','msg':'资料已更新'})
   ```
2. 如 User 模型没有 `email`/`phone`/`bio` 字段，先看现状决定加列（迁移）
3. `app/templates/` 新增 `my_profile.html` 简单编辑页（含改密跳转）
4. `base.html` 顶栏"用户名"右侧加"我的资料"入口（admin/普通用户通用）
5. `audit_screenshots/verify_f02_06_profile.py`：登录非 admin → 改电话 → 成功；admin 改非 admin → 审计日志含 before/after；任何人不改密码

**验收点**：
- 普通用户能改自己电话
- admin 改任何人有审计
- 任何人不通过此入口改密码

### BUG-F02-07（P2）主数据分页：物料/客户/供应商/仓库/部门 大数据量翻页慢、跳页跳不准、URL 参数不记忆

**现状**：
- `app/app.py` 5 个 list 函数均使用 `query.paginate(page, per_page, error_out=False)` 但没有 `per_page` 上限校验
- 模板 `_list_macros.html` 的 `pager()` 宏可能没有"每页 N 条"切换器
- URL 不记忆 sort/order/filter，刷新即丢

**修复方案**：
1. `_apply_pagination` 助手函数统一：限制 `per_page ∈ [10, 20, 50, 100, 200]`，默认 20，超过报错或截断
2. `_list_macros.html:pager()` 加每页 N 条下拉 + sort/order hidden input
3. 5 个 list 模板嵌入 `pager()` 宏
4. `audit_screenshots/verify_f02_07_pagination.py`：请求 `?per_page=999` → 截断到 200；`?per_page=10` → 10 条/页；点列头后 URL 含 sort/order

**验收点**：
- per_page 最大 200
- URL 含完整分页/排序/筛选参数
- 切换页号不掉

### BUG-F02-08（P2）标签模板权限体验：admin/warehouse 之外的角色（purchase/sales/production/user/viewer）看到设计按钮但点击 403，UX 不好

**现状**：
- `app/templates/label_template.html:80` 渲染"设计"按钮前已用 `{% if current_user.role in ['admin','warehouse'] %}` 守卫
- 但 `label_template_detail.html:322` "保存布局" 按钮**没有**同样守卫
- 实际：purchase 角色直接访问 `/label_template/1` URL 仍能进入设计页（路由仅 `@login_required`），点保存时才 403

**修复方案**：
1. `app/app.py:label_template_detail` 路由加 `@require_role('admin', 'warehouse')`
2. `label_template_detail.html` 整页（含"保存布局"按钮）包 `{% if current_user.role in ['admin','warehouse'] %}...{% else %}<div class="alert alert-warning">您没有模板设计权限</div>{% endif %}`
3. `audit_screenshots/verify_f02_08_template_perm.py`：purchase 角色 GET 模板详情 → 403；admin 角色 → 200

**验收点**：
- purchase/sales 等非授权角色访问模板设计页直接 403
- admin/warehouse 角色正常使用

## 修复顺序

按 P0 → P1 → P2 顺序：

1. **BUG-F02-03**（P0 标签模板静默覆盖 — 已 100% 影响数据安全，必须先修）
2. **BUG-F02-02**（P1 物料 API 截断 — 影响数据完整性）
3. **BUG-F02-06**（P1 用户资料编辑 — admin 改人有审计，但普通用户改自己没入口）
4. **BUG-F02-04**（P1 库位主数据/库存归属）
5. **BUG-F02-05**（P2 关闭库位管理后业务可用性）
6. **BUG-F02-01**（P2 基础资料排序）
7. **BUG-F02-07**（P2 主数据分页）
8. **BUG-F02-08**（P2 标签模板权限体验）

## 业务边界（硬约束）

- **不修改密码**：用户编辑/用户资料编辑入口**不包含**密码字段；密码修改走 `change_password` 独立路由
- **不猜测旧数据仓库归属**：库位迁移时如果历史 `LocationInventory.location` 对应的 Location 已被删除，**不自动重新分配**，标"未知库位"+ 让 admin 人工补
- **业务单据状态/库存仅由人工流程触发**：AI 不直接修改任何已提交/已完成的入库单、出库单、调拨单、盘点单、调整单
- **不新建分支**：所有 commit 都在 `main`（branch policy hard rule）
- **不删除已完成入库单**：AGENTS.md R-3 强规则
- **不重置/生成随机密码**：AGENTS.md R-1 强规则

## 每项 commit 规范

```bash
git add <changed files>
git commit -m "fix(F02-XX): <中文标题>

- 修复了什么（症状→根因→解决）
- 改动文件清单
- 验证命令
- 业务边界符合性声明"
git push origin main
```

例：
```bash
git commit -m "fix(F02-03): 标签模板保存布局路由缺失 + JS 误报成功

- 症状：拖完字段点保存，alert「布局保存成功」，实际数据丢失
- 根因：app.py 无 /label_template/<id>/save_layout 路由，label_template_detail.html:675 调用返回 404/405
- 解决：app.py 新增 save_label_template_layout（@require_role admin/warehouse + layout JSON 校验 + 审计 log）；label_template_detail.html saveLayout() 加 response.ok 检查 + 保存中 disabled 态
- 验证：audit_screenshots/verify_f02_03_label_save.py 4 项全绿；浏览器 E2E 拖动→保存→刷新→布局保留
- 边界：未改任何业务单据、未动密码、未新建分支"
```

## 验证脚本架构

每个 F02 BUG 一个独立 `audit_screenshots/verify_f02_XX_xxx.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_f02_XX_xxx.py — BUG-F02-XX 专项验证"""
import sys, os, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from start_server import BASE_URL, login

def main():
    op = login()
    print(f'===== BUG-F02-XX 验证 =====\n')
    results = []
    def check(name, cond, detail=''):
        results.append((cond, name, detail))
        mark = '✓' if cond else '✗'
        print(f'  [{mark}] {name}{(": "+detail) if detail and not cond else ""}')
    # ... 静态 + 动态 ...
    passed = sum(1 for ok,_,_ in results if ok)
    print(f'\n通过 {passed} / 总计 {len(results)}')
    sys.exit(0 if passed == len(results) else 1)

if __name__ == '__main__':
    main()
```

## 全量验证清单（8 BUG 完成后的回归）

```bash
# 启动服务
python audit_screenshots/start_server.py &

# 等启动完成
sleep 3

# 8 个专项
python audit_screenshots/verify_f02_01_sort.py
python audit_screenshots/verify_f02_02_truncate.py
python audit_screenshots/verify_f02_03_label_save.py
python audit_screenshots/verify_f02_04_location.py
python audit_screenshots/verify_f02_05_location_off.py
python audit_screenshots/verify_f02_06_profile.py
python audit_screenshots/verify_f02_07_pagination.py
python audit_screenshots/verify_f02_08_template_perm.py

# 浏览器 E2E（TRAE 集成浏览器）
# 截图存 audit_screenshots/f02_e2e/f02_NN_*.png
```

## 提交与推送节奏

每项 BUG：
1. 改代码（1~3 文件）
2. 写验证脚本 → 跑通
3. 浏览器 E2E 1~2 张截图
4. `git add` + `git commit` + `git push origin main`
5. 推进 todo
6. 全部 8 项完成后：
   - 更新 `WMS_BUG_BASELINE.md` 追加 8 条
   - 更新 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 把 F02 状态从"开发中"改"已完成"
   - 1 个收尾 commit

## 风险与回滚

- BUG-F02-03 新增路由 — 回滚：删除路由即可
- BUG-F02-06 新增 `email/phone/bio` 字段（如需）— 用 SQLAlchemy `db.Column` 新增 + `db.session.execute(text('ALTER TABLE user ADD COLUMN ...'))` 兼容老库
- BUG-F02-07 限制 per_page — 不影响存量数据，只是请求级校验
- BUG-F02-04 库位归属 — 不修改存量 LocationInventory，**只做新增逻辑**

## 不在本轮范围

- AI 自动入库（AGENTS.md R-2 强规则：仅可建草稿，不可自动提交/完成）
- 删除已完成入库单（AGENTS.md R-3 强规则）
- 修改 admin bootstrap 密码（AGENTS.md R-1 强规则）
- 新建/切换分支（AGENTS.md branch policy hard rule）
