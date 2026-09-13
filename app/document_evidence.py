import base64
import binascii
from datetime import datetime
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, ValidationError

from db import db


class DocumentEvidence(db.Model):
    __tablename__ = 'document_evidence'
    id = db.Column(db.Integer, primary_key=True)
    in_order_id = db.Column(db.Integer, db.ForeignKey('in_order.id'), nullable=True, index=True)
    out_order_id = db.Column(db.Integer, db.ForeignKey('out_order.id'), nullable=True, index=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    __table_args__ = (db.CheckConstraint(
        '(in_order_id IS NOT NULL AND out_order_id IS NULL) OR '
        '(in_order_id IS NULL AND out_order_id IS NOT NULL)', name='ck_evidence_one_document'),)


class EvidencePayload(BaseModel):
    evidence: list[str] = Field(default_factory=list, max_length=3)


def _decode_evidence(payload):
    try:
        request_data = EvidencePayload.model_validate(payload)
        images = []
        for encoded in request_data.evidence:
            if len(encoded) > 400000:
                return None, '照片过大，每张请压缩至300KB以内'
            raw = base64.b64decode(encoded, validate=True)
            with Image.open(BytesIO(raw)) as image:
                if image.format != 'JPEG' or image.width > 1600 or image.height > 1600:
                    return None, '照片必须为JPEG且长边不超过1600像素'
                image.load()
                with image.convert('RGB') as normalized:
                    output = BytesIO()
                    normalized.save(output, format='JPEG', quality=80)
            content = output.getvalue()
            if len(content) > 300000:
                return None, '照片内容过大，请降低分辨率后重试'
            images.append(content)
        return images, None
    except (ValidationError, ValueError, TypeError, binascii.Error, UnidentifiedImageError,
            OSError, Image.DecompressionBombError):
        return None, '取证照片格式无效，最多3张JPEG照片'


def _save_evidence(images, document_type, order_id, operator_id):
    for image in images:
        db.session.add(DocumentEvidence(
            in_order_id=order_id if document_type == 'in_order' else None,
            out_order_id=order_id if document_type == 'out_order' else None,
            operator_id=operator_id, image=image))
