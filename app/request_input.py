"""Typed boundaries for round26; routes never echo validation input values."""
# AI_FIX_TASK: AI-BROWSER-AUDIT-FIX-20261101-002
import math

from flask import request
from pydantic import BaseModel, Field, StrictInt, StrictStr, field_validator, model_validator


def json_object_body():
    """Allow a legacy empty body, but reject explicit null/scalars/invalid JSON."""
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return payload
    if not request.get_data(cache=True):
        return {}
    raise ValueError('JSON object required')


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
