"""
回归验证：手机端出库（扫码/手工）选填「合同编号」+ 快速匹配（2026-08-24 用户需求）

需求：
- 出库增加选填合同编号字段；
- 支持快速匹配：输入片段（如 0709）即可匹配完整合同编号（如 HD260709）；
- 合同编号为选填项。

配套改动：
- 后端新增 GET /api/mobile/contracts 模糊搜索（仅启用合同，ilike 片段匹配）；
- 后端 POST /api/outbound 接收 contract_no：命中档案回填 contract_id/project_name
  并同步到明细，未命中保留原文本，缺省不校验；
- Android：OutboundRequest 增加 contractNo；ScanViewModel 增加合同输入/防抖搜索/
  选中回填；OutboundScreen 增加合同输入卡片。

验收标准：
- T1: 后端存在 /api/mobile/contracts 路由且用 ilike 模糊匹配、仅 active 合同
- T2: 后端 /api/outbound 把合同字段写到 OutOrder 头与 OutOrderItem 明细
- T3: OutboundRequest 携带 contract_no
- T4: ScanViewModel 有防抖合同搜索（searchContracts + delay）且提交成功清空合同
- T5: OutboundScreen 有合同输入卡片且标注选填
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
BACKEND = WORKSPACE / "app/routes/native_api.py"
REQ = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/model/ScanRequests.kt"
VM = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel/scan/ScanViewModel.kt"
SCREEN = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ScanScreens.kt"


def _extract_fn(src: str, signature: str) -> str:
    m = re.search(signature, src)
    if not m:
        return ""
    nxt = src.find("@app.route(", m.end())
    return src[m.start(): nxt if nxt > 0 else len(src)]


def test_t1_backend_contracts_search_route():
    src = BACKEND.read_text(encoding="utf-8")
    assert "/api/mobile/contracts" in src, "缺少 /api/mobile/contracts 路由"
    body = _extract_fn(src, r"def\s+mobile_api_contracts_search\s*\(")
    assert body, "mobile_api_contracts_search 未找到"
    assert "ilike" in body, "合同搜索必须用 ilike 片段模糊匹配（0709 → HD260709）"
    assert "active" in body, "合同搜索必须仅返回启用（active）合同"


def test_t2_backend_outbound_writes_contract():
    src = BACKEND.read_text(encoding="utf-8")
    body = _extract_fn(src, r"def\s+native_api_outbound\s*\(")
    assert body, "native_api_outbound 未找到"
    assert "payload.get('contract_no')" in body, "outbound 未读取 contract_no"
    assert re.search(r"OutOrder\([\s\S]*?contract_no=order_contract_no", body), (
        "outbound 未把合同编号写入 OutOrder 头"
    )
    assert re.search(r"OutOrderItem\([\s\S]*?contract_no=order_contract_no", body), (
        "outbound 未把合同编号同步到 OutOrderItem 明细"
    )


def test_t3_outbound_request_has_contract_no():
    src = REQ.read_text(encoding="utf-8")
    assert '@SerializedName("contract_no")' in src and "contractNo" in src, (
        "OutboundRequest 缺少 contract_no 字段"
    )


def test_t4_viewmodel_debounced_search_and_clear_on_success():
    src = VM.read_text(encoding="utf-8")
    assert "searchContracts" in src, "ScanViewModel 缺少合同搜索"
    assert re.search(r"contractSearchJob\s*=\s*viewModelScope\.launch\s*\{\s*delay\(180\)", src), (
        "合同搜索必须防抖（delay 后发起），避免逐字符打满接口"
    )
    m = re.search(r"fun\s+submitOutbound[\s\S]*?contractNo\s*=\s*\"\"", src)
    assert m, "提交成功后必须清空合同编号（下一单不带入上一单合同）"


def test_t5_screen_has_contract_input_optional():
    src = SCREEN.read_text(encoding="utf-8")
    assert "ContractInputCard" in src, "OutboundScreen 缺少合同输入卡片"
    assert "合同编号（选填）" in src, "合同输入必须标注选填"


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
    print(f"\n所有 {len(tests)} 个出库合同编号回归验证通过")
