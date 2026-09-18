# -*- coding: utf-8 -*-
"""
BUG-2026-09-18-008 回归：手机端入库单头字段补全（供应商 / 合同号 / 备注）。

现象
----
现场用手机做「采购入库」后，PC 每日报表的「采购入库」列表里**供应商列永远空白**，
采购对账断链；单据备注也永远是一句系统常量，记不下送货单号。

根因
----
`/api/inbound`（`app/routes/native_api.py::native_api_inbound`）**只读明细行**，
`supplier_id` / `contract_no` / `remark` 三个 body 字段从未被读取；
构造 `InOrder(...)` 时 `purpose`/`remark` 直接写死常量。
而 `InOrder` 模型本就有 `supplier_id` / `contract_id` / `contract_no` / `project_name`
列（PC 端入库单在填），出库侧 `native_api_outbound` 早就读 `contract_no` 了，
只有入库侧漏掉了 —— 典型的「同一张单据，PC 有、手机没有」断链。

修复
----
1. 后端 `native_api_inbound` 读取三个字段：
   - `supplier_id`：命中 Supplier 写入 `InOrder.supplier_id`；**id 无效硬拒**
     （对齐 PC 行为 `请选择有效的供应商`，不静默丢弃）；
   - `supplier` / `supplier_name`：仅在无 id 时作为文本兜底匹配（编码或名称）；
   - `contract_no`：命中合同档案回填 `contract_id` / `project_name`，未建档保留原文；
   - `remark`：写入 `InOrder.remark`，留空仍回落旧常量（行为兼容）。
2. 新增 `GET /api/mobile/suppliers`（形状对齐 `api/departments`）作为下拽数据源。
3. Android：`InboundRequest` 增加 `supplier_id` / `supplier` / `contract_no` / `remark`；
   入库页 header 增加「供应商」选择卡 + 「备注」输入卡；
   两者一并进 `ScanEditDraft` 断点续传快照（否则进程被回收会静默丢供应商关联）。

生效条件
--------
后端改动**需重启 WMS 服务生效（R3）**；Android 改动需重新构建并安装 APK。
"""
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NATIVE_API = os.path.join(REPO, 'app', 'routes', 'native_api.py')
SCAN_REQUESTS = os.path.join(
    REPO, 'app', 'android-native-wms', 'app', 'src', 'main', 'java',
    'com', 'factory', 'wms', 'data', 'model', 'ScanRequests.kt')
SCAN_EDIT_DRAFT = os.path.join(
    REPO, 'app', 'android-native-wms', 'app', 'src', 'main', 'java',
    'com', 'factory', 'wms', 'data', 'model', 'ScanEditDraft.kt')
SCAN_VIEW_MODEL = os.path.join(
    REPO, 'app', 'android-native-wms', 'app', 'src', 'main', 'java',
    'com', 'factory', 'wms', 'ui', 'viewmodel', 'scan', 'ScanViewModel.kt')
SCAN_SCREENS = os.path.join(
    REPO, 'app', 'android-native-wms', 'app', 'src', 'main', 'java',
    'com', 'factory', 'wms', 'ui', 'screens', 'ScanScreens.kt')
WMS_API_SERVICE = os.path.join(
    REPO, 'app', 'android-native-wms', 'app', 'src', 'main', 'java',
    'com', 'factory', 'wms', 'data', 'api', 'WmsApiService.kt')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _extract_inbound_endpoint(src):
    """截取 native_api_inbound 函数体（到下一个 def 或文件尾）。"""
    m = re.search(r'\n    def native_api_inbound\([^)]*\):(.*?)(?=\n    def |\Z)', src, re.S)
    assert m, 'native_api.py 中找不到 native_api_inbound 函数'
    return m.group(1)


def _brace_balance(text):
    """朴素括号平衡（剔除字符串字面量与行注释），兜底防结构性破坏。"""
    depth = 0
    # 去掉三引号块
    cleaned = re.sub(r'""".*?"""', '', text, flags=re.S)
    cleaned = re.sub(r"'''.*?'''", '', cleaned, flags=re.S)
    for line in cleaned.splitlines():
        line = re.sub(r'#.*$', '', line)
        line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
        line = re.sub(r"'(?:[^'\\]|\\.)*'", "''", line)
        depth += line.count('(') - line.count(')')
    return depth


# ---------------------------------------------------------------- T1 后端读字段
def test_t1_backend_reads_header_fields():
    """后端必须真的读 supplier_id / contract_no / remark，而不是只读明细行。"""
    body = _extract_inbound_endpoint(_read(NATIVE_API))
    assert "payload.get('supplier_id')" in body, \
        'native_api_inbound 未读取 supplier_id（BUG-2026-09-18-008 根因）'
    assert "payload.get('contract_no')" in body, \
        'native_api_inbound 未读取 contract_no'
    assert "payload.get('remark')" in body, \
        'native_api_inbound 未读取 remark'
    # supplier 文本兜底也要在
    assert "payload.get('supplier')" in body and "payload.get('supplier_name')" in body, \
        'native_api_inbound 缺少 supplier / supplier_name 文本兜底'


# ---------------------------------------------------------------- T2 写入 InOrder
def test_t2_backend_writes_header_fields_into_inorder():
    """读到的值必须落到 InOrder(...) 构造里，否则等于没读。"""
    body = _extract_inbound_endpoint(_read(NATIVE_API))
    for field in ('supplier_id=', 'contract_id=', 'contract_no=', 'project_name='):
        assert field in body, \
            f'InOrder(...) 构造缺少 {field}（读了没写 = 无效修复）'
    # remark 不能再写死常量，必须来自入参变量
    assert 'remark=remark_input' in body, \
        'InOrder.remark 未接到用户入参 remark_input（仍写死常量）'


# ------------------------------------------------------- T3 无效供应商 id 硬拒
def test_t3_invalid_supplier_id_hard_rejected():
    """无效 supplier_id 必须硬拒，不能静默丢失（对齐 PC '请选择有效的供应商'）。"""
    body = _extract_inbound_endpoint(_read(NATIVE_API))
    # 必须是"查无此供应商 → return api_json_error(...)"，而不是静默置 None 继续下单
    assert re.search(
        r"if supplier is None:\s*\n\s*return api_json_error\('请选择有效的供应商'",
        body), \
        "缺少无效供应商 id 的硬拒分支（应为 `if supplier is None: return api_json_error(...)`），" \
        "静默丢弃会让报表供应商列恒为空"


# ------------------------------------------------- T4 合同号回填 contract_id
def test_t4_contract_no_backfills_contract_id_and_project():
    """命中合同档案时回填 contract_id/project_name；未建档时保留用户原文。"""
    body = _extract_inbound_endpoint(_read(NATIVE_API))
    assert 'Contract.query.filter' in body, '未按 contract_no 查合同档案'
    assert 'order_contract_id' in body and 'order_project_name' in body, \
        '未生成 contract_id / project_name 回填变量'
    # 未命中时保留原文（contract_no_input），不能把用户输入吞掉
    assert re.search(r'order_contract_no\s*=\s*\(?.*contract_no_input', body), \
        '未建档合同号未保留用户原文'


# ------------------------------------------------------- T5 供应商数据源接口
def test_t5_suppliers_endpoint_exists():
    """新增 GET /api/mobile/suppliers（形状对齐 api/departments）。"""
    src = _read(NATIVE_API)
    assert "/api/mobile/suppliers" in src, '缺少 /api/mobile/suppliers 路由'
    assert re.search(r'\n    def native_api_suppliers\([^)]*\):', src), \
        '缺少 native_api_suppliers 处理函数'
    m = re.search(r'\n    def native_api_suppliers\([^)]*\):(.*?)(?=\n    def |\Z)', src, re.S)
    body = m.group(1)
    assert 'Supplier.query' in body, '未查询 Supplier 表'
    assert "'items'" in body, "响应未按统一信封返回 data.items"


# ------------------------------------------------- T6 Android 请求体带四字段
def test_t6_android_inbound_request_has_new_fields():
    """InboundRequest 必须新增 supplier_id / supplier / contract_no / remark。"""
    src = _read(SCAN_REQUESTS)
    m = re.search(r'data class InboundRequest\((.*?)\n\)', src, re.S)
    assert m, 'ScanRequests.kt 找不到 InboundRequest'
    body = m.group(1)
    for ser, prop in (
        ('supplier_id', 'supplierId'),
        ('contract_no', 'contractNo'),
    ):
        assert f'@SerializedName("{ser}")' in body and prop in body, \
            f'InboundRequest 缺少 {prop}（@SerializedName("{ser}")）'
    assert 'val supplier: String?' in body, 'InboundRequest 缺少 supplier 文本兜底字段'
    assert 'val remark: String?' in body, 'InboundRequest 缺少 remark'


# ------------------------------------------------- T7 构造点真的把字段传下去
def test_t7_viewmodel_passes_fields_at_construction_site():
    """ScanViewModel 构造 InboundRequest 时必须把值接上，不能只加字段不用。"""
    src = _read(SCAN_VIEW_MODEL)
    m = re.search(r'val request = InboundRequest\((.*?)\n\s*\)', src, re.S)
    assert m, 'ScanViewModel 找不到 InboundRequest(...) 构造点'
    body = m.group(1)
    for prop in ('supplierId =', 'supplier =', 'contractNo =', 'remark ='):
        assert prop in body, f'InboundRequest 构造点未传 {prop}（字段加了但没接线）'
    assert 'selectedSupplier' in body, 'supplierId/supplier 未取自 selectedSupplier 状态'


# ------------------------------------------------ T8 断点续传快照不丢单头数据
def test_t8_edit_draft_persists_supplier_and_remark():
    """供应商/备注必须进编辑草稿快照 + 恢复，否则进程回收后静默丢关联。"""
    draft = _read(SCAN_EDIT_DRAFT)
    m = re.search(r'data class ScanEditDraft\((.*?)\n\)', draft, re.S)
    assert m, 'ScanEditDraft.kt 找不到 ScanEditDraft'
    body = m.group(1)
    assert 'val supplier: SupplierDto?' in body, 'ScanEditDraft 未持久化 supplier'
    assert 'val inboundRemark: String' in body, 'ScanEditDraft 未持久化 inboundRemark'

    vm = _read(SCAN_VIEW_MODEL)
    # 快照点
    assert 'state.selectedSupplier' in vm, 'editDraftSnapshot 未采集 selectedSupplier'
    assert 'state.inboundRemark' in vm, 'editDraftSnapshot 未采集 inboundRemark'
    # 恢复点
    assert 'selectedSupplier = draft.supplier' in vm, 'restoreEditDraft 未回填 supplier'
    assert 'inboundRemark = draft.inboundRemark' in vm, 'restoreEditDraft 未回填 inboundRemark'


# ------------------------------------------------- T9 入库页有供应商与备注入口
def test_t9_inbound_ui_has_supplier_and_remark_entry():
    """入库页必须给用户选供应商 / 填备注的入口，否则后端接口没人用。"""
    src = _read(SCAN_SCREENS)
    # 供应商选择卡在 header 里
    assert 'label = "供应商（选填）"' in src, '入库页缺少「供应商（选填）」选择卡'
    assert 'viewModel.loadSuppliers()' in src, '入库页未加载供应商列表'
    # 备注输入卡
    assert 'InboundRemarkCard' in src, '入库页缺少备注输入卡'
    assert 'onInboundRemarkChange' in src, '备注输入未接到 ViewModel'


# ------------------------------------------------- T10 接口声明存在
def test_t10_api_service_declares_suppliers():
    """Retrofit 接口必须声明 getSuppliers，否则 Repository 调不通。"""
    src = _read(WMS_API_SERVICE)
    assert '@GET("api/mobile/suppliers")' in src, 'WmsApiService 未声明 api/mobile/suppliers'
    assert 'fun getSuppliers()' in src, 'WmsApiService 未声明 getSuppliers()'


# ------------------------------------------------------------ T11 括号平衡兜底
def test_t11_brace_balance():
    """结构性破坏兜底：三个 Kotlin 源文件括号应平衡。"""
    for path in (SCAN_REQUESTS, SCAN_EDIT_DRAFT, SCAN_SCREENS):
        assert _brace_balance(_read(path)) == 0, f'{os.path.basename(path)} 括号不平衡'
    # Python 侧用 ast 做真实语法校验
    import ast
    ast.parse(_read(NATIVE_API))
