"""
回归测试：P1-C 修复 - DocumentOcrResult.extracted 自我引用

审计报告位置：docs/Android_Mobile_App_Code_Audit_Report_2026-08-09.md §4.2.3 / §6 P1-C
BUG 模式：`val extracted: DocumentOcrResult?` 是自我引用递归类型
影响：Gson 在反序列化时遇到非 null 的 `extracted` 字段会尝试递归解析，
可能栈溢出或解析出错误结构。

修复：
- DocumentOcrResult.extracted 改为具体类型 ExtractedDocument?
- ExtractedDocument 字段对齐后端 api_document_ocr 实际返回的 dict 结构

验收标准：
- T1: WmsApiService.kt 中 `extracted: DocumentOcrResult?` 必须清零
- T2: 必须存在 `data class ExtractedDocument` 定义
- T3: DocumentOcrResult.extracted 引用 ExtractedDocument
- T4: ExtractedDocument 必须有 @SerializedName("document_type") 桥接字段
- T5: ExtractedDocument 必须有 @SerializedName("order_no") 和 purchase_order_no
- T6: ExtractedDocument 与 DocumentOcrResult 不应构成自引用环
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
API_FILE = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/api/WmsApiService.kt"


def _src() -> str:
    return API_FILE.read_text(encoding="utf-8")


def _strip_comments(src: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    no_line = re.sub(r"//[^\n]*", "", no_block)
    return no_line


def _extract_data_class_body(src: str, class_name: str) -> str:
    """提取 data class ClassName(...) 的 ( ... ) 内的字段声明文本。"""
    m = re.search(rf"data\s+class\s+{class_name}\s*\(", src)
    if not m:
        return ""
    paren_start = src.find("(", m.start())
    if paren_start < 0:
        return ""
    depth = 0
    end = paren_start
    for i in range(paren_start, len(src)):
        c = src[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    return src[paren_start + 1: end]


# ---------- T1: `extracted: DocumentOcrResult?` 必须清零 ----------
def test_t1_no_self_reference_extracted_field():
    """`val extracted: DocumentOcrResult?` 自我引用必须清零。"""
    src = _src()
    assert not re.search(
        r"val\s+extracted\s*:\s*DocumentOcrResult\s*\?",
        src,
    ), (
        "DocumentOcrResult.extracted 仍为 DocumentOcrResult? 自我引用类型；"
        "必须改为具体类型 ExtractedDocument?，避免 Gson 递归反序列化风险"
    )


# ---------- T2: 必须存在 data class ExtractedDocument ----------
def test_t2_extracted_document_class_exists():
    """必须存在 `data class ExtractedDocument` 定义。"""
    src = _src()
    assert re.search(r"data\s+class\s+ExtractedDocument\s*\(", src), (
        "未找到 data class ExtractedDocument 定义；"
        "DocumentOcrResult.extracted 改为 ExtractedDocument? 时必须提供具体类型"
    )


# ---------- T3: DocumentOcrResult.extracted 引用 ExtractedDocument ----------
def test_t3_document_ocr_result_uses_extracted_document():
    """DocumentOcrResult.extracted 字段必须声明为 ExtractedDocument?。"""
    src = _src()
    body = _extract_data_class_body(src, "DocumentOcrResult")
    assert body, "DocumentOcrResult 数据类未找到"
    assert re.search(
        r"\bval\s+extracted\s*:\s*ExtractedDocument\s*\?",
        body,
    ), (
        "DocumentOcrResult.extracted 字段必须声明为 `val extracted: ExtractedDocument?`，"
        "而不是自我引用 DocumentOcrResult?"
    )


# ---------- T4: ExtractedDocument 必须有 document_type 字段 ----------
def test_t4_extracted_document_has_document_type_serialized_name():
    """ExtractedDocument.documentType 必须有 @SerializedName(\"document_type\") 桥接。"""
    src = _src()
    body = _extract_data_class_body(src, "ExtractedDocument")
    assert body, "ExtractedDocument 数据类未找到"
    assert re.search(
        r'@SerializedName\(\s*"document_type"\s*\)\s+val\s+documentType\s*:\s*String\s*\?',
        body,
    ), (
        "ExtractedDocument.documentType 必须用 @SerializedName(\"document_type\") 桥接，"
        "与后端 API 响应字段名一致"
    )


# ---------- T5: ExtractedDocument 包含 order_no 和 purchase_order_no 字段 ----------
def test_t5_extracted_document_has_order_no_and_purchase_order_no():
    """ExtractedDocument 必须包含 orderNo (order_no) 和 purchaseOrderNo (purchase_order_no)。"""
    src = _src()
    body = _extract_data_class_body(src, "ExtractedDocument")
    assert body, "ExtractedDocument 数据类未找到"
    assert re.search(
        r'@SerializedName\(\s*"order_no"\s*\)\s+val\s+orderNo\s*:\s*String\s*\?',
        body,
    ), "ExtractedDocument.orderNo 必须用 @SerializedName(\"order_no\") 桥接"
    assert re.search(
        r'@SerializedName\(\s*"purchase_order_no"\s*\)\s+val\s+purchaseOrderNo\s*:\s*String\s*\?',
        body,
    ), "ExtractedDocument.purchaseOrderNo 必须用 @SerializedName(\"purchase_order_no\") 桥接"


# ---------- T6: ExtractedDocument 与 DocumentOcrResult 不构成自引用环 ----------
def test_t6_no_circular_reference_cycle():
    """ExtractedDocument 字段中不得出现 DocumentOcrResult 或 ExtractedDocument 自身。
    DocumentOcrResult 中 extracted 字段仅指向 ExtractedDocument（非自引用）。"""
    src = _src()
    body_extracted = _extract_data_class_body(src, "ExtractedDocument")
    assert body_extracted, "ExtractedDocument 数据类未找到"
    # ExtractedDocument 不得引用自身或 DocumentOcrResult（避免新的递归环）
    assert ": ExtractedDocument" not in body_extracted, (
        "ExtractedDocument 不得引用自身 ExtractedDocument?（防止新的递归环）"
    )
    assert ": DocumentOcrResult" not in body_extracted, (
        "ExtractedDocument 不得引用 DocumentOcrResult（防止递归环）"
    )


# ---------- T7: OcrItem 字段命名一致性（同时验证依赖项存在） ----------
def test_t7_extracted_document_reuses_ocr_item():
    """ExtractedDocument.items 应当复用现有 OcrItem 类型（与后端 items 数组元素一致）。"""
    src = _src()
    body = _extract_data_class_body(src, "ExtractedDocument")
    assert body, "ExtractedDocument 数据类未找到"
    assert re.search(r"\bval\s+items\s*:\s*List<OcrItem>\s*\?", body), (
        "ExtractedDocument.items 应当声明为 List<OcrItem>?，与后端 items 数组结构对齐"
    )


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failures.append(t.__name__)
    if failures:
        sys.exit(1)
    print(f"\n所有 {len(tests)} 个 P1-C 回归测试通过")
