"""Typed document and round26 JSON boundaries; never echo invalid input values."""
# AI_FIX_TASK: AI-BROWSER-AUDIT-FIX-20261101-002
import math
import json

from flask import jsonify, request
from pydantic import BaseModel, Field, StrictInt, StrictStr, field_validator, model_validator

STOCK_FIELD_LABELS = {
    'id': '明细标识', 'order_id': '单据标识', 'material_id': '物料标识',
    'supplier_id': '供应商', 'customer_id': '客户', 'department_id': '部门',
    'warehouse_id': '仓库', 'contract_id': '合同', 'order_no': '单据编号',
    'date': '日期', 'business_type': '业务类型', 'purpose': '用途',
    'warehouse': '仓库', 'location': '库位', 'remark': '备注',
    'contract_no': '合同编号', 'project_name': '工程名称', 'box_no': '箱体编号',
    'customer': '客户', 'picker': '领料人', 'code': '物料编码',
    'material_code': '物料编码', 'batch_no': '批次号', 'expiry_date': '有效期',
    'quantity': '数量', 'price': '单价', 'items': '明细',
    'source_in_order_no': '来源入库单号', 'source_in_order_id': '来源入库单',
    'source_purchase_order_item_id': '来源采购订单明细',
    'source_sales_order_item_id': '来源销售订单明细',
    'source_in_order_item_id': '来源入库明细',
    'doc_id': '单据标识', 'from_warehouse': '调出仓库', 'to_warehouse': '调入仓库',
    'from_location': '调出库位', 'to_location': '调入库位', 'area': '盘点区域',
    'transfer_no': '调拨单号', 'check_no': '盘点单号', 'request_no': '申请单号',
    'req_no': '领料单号', 'applicant': '申请人', 'department': '部门',
    'urgency': '紧急程度', 'expected_date': '期望日期', 'production_order': '工单',
    'contact': '联系人', 'phone': '电话', 'customer_feedback': '客户反馈',
    'responsibility': '责任归属', 'deadline': '截止日期', 'reason': '原因',
    'supplier': '供应商', 'supplier_name': '供应商名称', 'material_name': '物料名称',
    'spec': '规格', 'project_no': '工程编号', 'serial_no': '序列号',
    'currency': '币种', 'settlement_method': '结算方式', 'content': '粘贴内容',
    'actual_stock': '实盘数量', 'estimated_price': '预计单价', 'scrap_quantity': '报废数量',
}


def json_object_body():
    """Allow a legacy empty body, but reject explicit null/scalars/invalid JSON."""
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return payload
    if not request.get_data(cache=True):
        return {}
    raise ValueError('JSON object required')


class StockDocumentItemInput(BaseModel):
    id: int | None = None
    material_id: int | None = None
    contract_id: int | None = None
    source_purchase_order_item_id: int | None = None
    source_sales_order_item_id: int | None = None
    source_in_order_item_id: int | None = None
    quantity: float | None = None
    price: float | None = None
    actual_stock: float | None = None
    estimated_price: float | None = None
    scrap_quantity: float | None = None
    code: StrictStr | None = Field(None, max_length=50)
    material_code: StrictStr | None = Field(None, max_length=50)
    remark: StrictStr | None = Field(None, max_length=500)
    location: StrictStr | None = Field(None, max_length=100)
    contract_no: StrictStr | None = Field(None, max_length=50)
    project_name: StrictStr | None = Field(None, max_length=200)
    batch_no: StrictStr | None = Field(None, max_length=50)
    box_no: StrictStr | None = Field(None, max_length=100)
    expiry_date: StrictStr | None = Field(None, max_length=10)
    material_name: StrictStr | None = None
    spec: StrictStr | None = None
    area: StrictStr | None = None
    reason: StrictStr | None = None
    supplier: StrictStr | None = None
    supplier_name: StrictStr | None = None
    project_no: StrictStr | None = None
    serial_no: StrictStr | None = None

    @field_validator('*', mode='before')
    @classmethod
    def stock_field_type(cls, value, info):
        if info.field_name == 'id' or info.field_name.endswith('_id'):
            if value is None or value in ('', 'None', 'null'):
                return None
            if type(value) is int and 0 <= value < 2**63:
                return value
            if isinstance(value, str) and len(value) <= 19 and value.isdecimal() and int(value) < 2**63:
                return int(value)
            raise ValueError('Integer identifier required')
        if info.field_name in ('quantity', 'price', 'actual_stock', 'estimated_price', 'scrap_quantity') and value is not None:
            if info.field_name != 'quantity' and isinstance(value, str) and not value.strip():
                return None
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                raise ValueError('Finite numeric value required')
            try:
                number = float(value)
            except (ValueError, OverflowError):
                raise ValueError('Finite numeric value required') from None
            if not math.isfinite(number):
                raise ValueError('Finite numeric value required')
        return value


class DocumentHeaderInput(StockDocumentItemInput):
    """Validate text before legacy stock routes call strip or mutate ORM rows."""
    order_no: StrictStr | None = Field(None, max_length=50)
    date: StrictStr | None = Field(None, max_length=10)
    business_type: StrictStr | None = Field(None, max_length=50)
    purpose: StrictStr | None = Field(None, max_length=200)
    warehouse: StrictStr | None = Field(None, max_length=100)
    customer: StrictStr | None = Field(None, max_length=100)
    picker: StrictStr | None = Field(None, max_length=50)
    source_in_order_no: StrictStr | None = Field(None, max_length=50)
    order_id: int | None = None
    supplier_id: int | None = None
    customer_id: int | None = None
    department_id: int | None = None
    warehouse_id: int | None = None
    source_in_order_id: int | None = None
    doc_id: int | None = None
    from_warehouse: StrictStr | None = None
    to_warehouse: StrictStr | None = None
    from_location: StrictStr | None = None
    to_location: StrictStr | None = None
    transfer_no: StrictStr | None = None
    check_no: StrictStr | None = None
    request_no: StrictStr | None = None
    req_no: StrictStr | None = None
    applicant: StrictStr | None = None
    department: StrictStr | None = None
    urgency: StrictStr | None = None
    expected_date: StrictStr | None = None
    production_order: StrictStr | None = None
    contact: StrictStr | None = None
    phone: StrictStr | None = None
    customer_feedback: StrictStr | None = None
    responsibility: StrictStr | None = None
    deadline: StrictStr | None = None
    currency: StrictStr | None = None
    settlement_method: StrictStr | None = None
    content: StrictStr | None = None


class StockDocumentInput(DocumentHeaderInput):
    remark: StrictStr | None = Field(None, max_length=200)
    items: list[StockDocumentItemInput] = Field(default_factory=list)


class DocumentItemInput(StockDocumentItemInput):
    # Sales batches have a 100-character column; inbound keeps its 50 limit.
    batch_no: StrictStr | None = Field(None, max_length=100)


class DocumentContentInput(DocumentHeaderInput):
    header: DocumentHeaderInput | None = None
    items: list[DocumentItemInput] | None = None


class OpeningLineEditInput(StockDocumentItemInput):
    revision: StrictStr | None = None


STOCK_DOCUMENT_JSON_ENDPOINTS = frozenset({
    'add_in_order', 'update_in_order', 'add_in_order_item',
    'batch_add_in_order_items', 'update_in_order_item', 'update_completed_in_order',
    'add_out_order', 'update_out_order', 'add_out_order_item',
    'batch_add_out_order_items', 'update_out_order_item',
})


def validate_document_json_input():
    """Authorized JSON is validated before revision checks or ORM mutations."""
    if request.method != 'POST' or not request.is_json:
        return None
    if request.endpoint in STOCK_DOCUMENT_JSON_ENDPOINTS:
        schema = StockDocumentInput
    elif request.endpoint == 'add_adjustment':
        schema = AdjustmentSaveInput
    else:
        from services.document_edit_guard import EDIT_ENDPOINTS
        if request.endpoint not in EDIT_ENDPOINTS | {
                'sales_order_add', 'add_subcontract', 'add_subcontract_issue',
                'add_subcontract_receive', 'add_opening_stock'}:
            return None
        schema = DocumentContentInput
    try:
        payload = json_object_body()
        # These two established sales handlers also accept JSON-encoded items.
        # Validate a copy and preserve the actual request format for the view.
        if request.endpoint in ('sales_order_add', 'sales_order_edit') and isinstance(payload.get('items'), str):
            payload = dict(payload, items=json.loads(payload['items'] or '[]'))
        schema.model_validate(payload)
    except (ValueError, TypeError) as error:
        if schema is AdjustmentSaveInput:
            return jsonify(status='error', msg='调整单参数格式不正确，请检查文本、编号和明细数量'), 400
        field = '请求内容'
        if hasattr(error, 'errors'):
            location = error.errors(include_input=False)[0]['loc']
            if location:
                field = STOCK_FIELD_LABELS.get(location[-1], '请求内容')
                if len(location) > 1 and location[0] == 'items' and isinstance(location[1], int):
                    field = f'第{location[1]+1}行{field}'
        return jsonify(status='error', code='INVALID_DOCUMENT_INPUT',
                       msg=f'字段 {field} 格式或长度不正确，请检查后重试'), 400
    return None


class ForecastInput(BaseModel):
    forecast_days: StrictInt = 30
    category: StrictStr = Field('', max_length=100)

    @field_validator('forecast_days')
    @classmethod
    def supported_period(cls, value):
        if value not in (7, 14, 30):
            raise ValueError('Unsupported period')
        return value


class CheckCompleteInput(BaseModel):
    force: bool = False

    @field_validator('force', mode='before')
    @classmethod
    def explicit_force(cls, value):
        if value is None or value == '':
            return False
        if type(value) is bool:
            return value
        if type(value) is int and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ('1', 'true', 'yes'):
                return True
            if normalized in ('0', 'false', 'no'):
                return False
        raise ValueError('Explicit boolean required')


class MaterialImageInput(BaseModel):
    image_url: StrictStr = Field('', max_length=4096)


class AcceptanceEvidenceInput(BaseModel):
    days: StrictInt = Field(7, ge=1, le=30)
    end_date: StrictStr = Field('', max_length=10)


class AdjustmentItemInput(BaseModel):
    material_id: int | None = None
    code: StrictStr = Field('', max_length=50)
    material_code: StrictStr = Field('', max_length=50)
    quantity: float = Field(..., gt=0, le=999999)
    location: StrictStr = Field('', max_length=100)
    reason: StrictStr = Field('', max_length=500)

    @field_validator('material_id', mode='before')
    @classmethod
    def positive_material_id(cls, value):
        if value is None or value == '':
            return None
        if type(value) is int and 0 < value < 2**63:
            return value
        if isinstance(value, str) and value.isdecimal() and 0 < int(value) < 2**63:
            return int(value)
        raise ValueError('Positive material ID required')

    @field_validator('quantity', mode='before')
    @classmethod
    def finite_quantity(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError('Finite numeric quantity required')
        try:
            number = float(value)
        except (ValueError, OverflowError):
            raise ValueError('Finite numeric quantity required') from None
        if not math.isfinite(number):
            raise ValueError('Finite numeric quantity required')
        return number

    @field_validator('code', 'material_code', 'location', 'reason', mode='before')
    @classmethod
    def optional_item_text(cls, value):
        return '' if value is None else value


class AdjustmentSaveInput(BaseModel):
    order_id: int | None = None
    id: int | None = None
    adjustment_no: StrictStr = Field('', max_length=50)
    adjustment_type: StrictStr = Field('', max_length=20)
    date: StrictStr = Field('', max_length=10)
    remark: StrictStr = Field('', max_length=500)
    warehouse: StrictStr = Field('', max_length=100)
    warehouse_id: int | None = None
    items: list[AdjustmentItemInput] = Field(default_factory=list)

    @field_validator('order_id', 'id', 'warehouse_id', mode='before')
    @classmethod
    def optional_positive_id(cls, value):
        if value is None or value in ('', 'None', 'null'):
            return None
        if type(value) is int and 0 < value < 2**63:
            return value
        if isinstance(value, str) and value.isdecimal() and 0 < int(value) < 2**63:
            return int(value)
        raise ValueError('Positive ID required')

    @field_validator('adjustment_no', 'adjustment_type', 'date', 'remark', 'warehouse', mode='before')
    @classmethod
    def optional_header_text(cls, value):
        return '' if value is None else value

    @model_validator(mode='after')
    def consistent_document_id(self):
        if self.order_id is not None and self.id is not None and self.order_id != self.id:
            raise ValueError('Conflicting document identifiers')
        return self
