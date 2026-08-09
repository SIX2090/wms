"""
回归测试：P1-A 修复 - submitStocktake 仓库必填校验

审计报告位置：docs/Android_Mobile_App_Code_Audit_Report_2026-08-09.md §3.4 / §6 P1-A
BUG 模式：盘点提交未校验仓库，与 AGENTS.md "仓库必填" 规则不一致

验收标准：
- T1: submitStocktake 体内出现 `selectedWarehouse == null` 校验
- T2: 校验失败时设置 `error = "请选择仓库"`
- T3: StocktakeRequest 数据类增加 warehouse / warehouse_code 字段
- T4: 校验顺序：仓库为空 -> 立即 return（不会继续往下走）
- T5: 旧代码 "submitStocktake" 体内不出现"无 warehouse 校验"的旧路径
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SCAN_VM = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel/scan/ScanViewModel.kt"
SCAN_REQ = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/model/ScanRequests.kt"


def _src(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _strip_comments_for_presence_check(src: str) -> str:
    """剥离块注释和行注释，但保留字符串字面量；用于"是否存在某 API"的判断。"""
    # 移除 /* ... */ 块注释
    no_block = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    # 移除 // 行注释
    no_line = re.sub(r"//[^\n]*", "", no_block)
    return no_line


def _extract_function_body(src: str, func_name: str) -> str:
    """提取顶层 fun func_name(...) { ... } 的函数体文本（基于大括号配平）。"""
    # 匹配 fun func_name( ... ) { 起始
    m = re.search(rf"fun\s+{func_name}\s*\(", src)
    if not m:
        return ""
    # 找到第一个 { 位置
    brace_start = src.find("{", m.end())
    if brace_start < 0:
        return ""
    depth = 0
    i = brace_start
    while i < len(src):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[brace_start: i + 1]
        i += 1
    return ""


# ---------- T1: submitStocktake 体内出现仓库空校验 ----------
def test_t1_submitstocktake_validates_warehouse_null():
    """submitStocktake 函数体内必须出现仓库空校验（state.selectedWarehouse 或
    局部变量 warehouse == null）"""
    src = _src(SCAN_VM)
    body = _extract_function_body(src, "submitStocktake")
    assert body, "submitStocktake 函数未找到"
    # 两种合法写法都接受：
    #   if (state.selectedWarehouse == null) { ... }
    #   val warehouse = state.selectedWarehouse; if (warehouse == null) { ... }
    has_direct = re.search(r"selectedWarehouse\s*==\s*null", body) is not None
    has_indirect = (
        re.search(r"val\s+warehouse\s*=\s*state\.selectedWarehouse", body) is not None
        and re.search(r"warehouse\s*==\s*null", body) is not None
    )
    assert has_direct or has_indirect, (
        "submitStocktake 缺少 selectedWarehouse == null 校验；"
        "必须与 submitInbound/submitOutbound 一致，先校验仓库必填"
    )


# ---------- T2: 校验失败时 error = "请选择仓库" ----------
def test_t2_warehouse_null_sets_error_msg():
    """仓库空校验失败时必须把 error 置为 "请选择仓库"，与入库/出库一致"""
    src = _src(SCAN_VM)
    body = _extract_function_body(src, "submitStocktake")
    assert body, "submitStocktake 函数未找到"
    # 在仓库空校验分支内必须出现 error = "请选择仓库"
    # 允许 selectedWarehouse 或局部变量 warehouse
    # 容忍空白和换行
    pattern = (
        r"(warehouse\s*==\s*null|selectedWarehouse\s*==\s*null)"
        r"[\s\S]{0,200}?"
        r'error\s*=\s*"请选择仓库"'
    )
    assert re.search(pattern, body), (
        "submitStocktake 的仓库校验失败分支必须 error = \"请选择仓库\"，"
        "与 submitInbound/submitOutbound 文案保持一致"
    )


# ---------- T3: StocktakeRequest 增加 warehouse / warehouse_code 字段 ----------
def test_t3_stocktake_request_has_warehouse_fields():
    """StocktakeRequest 数据类必须包含 warehouse 和 warehouse_code 字段"""
    src = _src(SCAN_REQ)
    # 找到 data class StocktakeRequest 的左括号位置（注意正则已吞掉一个 "("）
    m = re.search(r"data\s+class\s+StocktakeRequest\s*\(", src)
    assert m, "StocktakeRequest 数据类未找到"
    # m.end() 指向 class 第一个 ( 之后的位置；这里 ( 已经在 regex 里被消费。
    # 我们从 m.start() 之后找到第一个 ( 作为 data class 的左括号起点。
    paren_start = src.find("(", m.start())
    assert paren_start >= 0
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
    body = src[paren_start + 1: end]
    # 必须有 warehouse: String? = null
    assert re.search(r"\bwarehouse\s*:\s*String\s*\?\s*=\s*null\b", body), (
        "StocktakeRequest 必须声明 warehouse: String? = null 字段"
    )
    # 必须有 @SerializedName(\"warehouse_code\") val warehouseCode: String? = null
    assert re.search(
        r'@SerializedName\(\s*"warehouse_code"\s*\)\s+val\s+warehouseCode\s*:\s*String\s*\?\s*=\s*null',
        body,
    ), (
        "StocktakeRequest 必须声明 @SerializedName(\"warehouse_code\") val warehouseCode: String? = null 字段"
    )


# ---------- T4: 校验顺序：仓库为空 -> return ----------
def test_t4_warehouse_check_before_lines_check():
    """submitStocktake 必须先校验仓库，再校验 lines.isEmpty，避免先返"请先扫描盘点物料"误导用户"""
    src = _src(SCAN_VM)
    body = _extract_function_body(src, "submitStocktake")
    assert body, "submitStocktake 函数未找到"
    # 仓库校验：直接 selectedWarehouse == null 或 局部变量 warehouse == null
    m_wh = (
        re.search(r"selectedWarehouse\s*==\s*null", body)
        or (
            re.search(r"val\s+warehouse\s*=\s*state\.selectedWarehouse", body)
            and re.search(r"warehouse\s*==\s*null", body)
        )
    )
    m_lines = re.search(r"lines\.isEmpty\(\)", body)
    assert m_wh and m_lines, "submitStocktake 缺少仓库/lines 校验"
    # 必须有 selectedWarehouse 的赋值（用于定位仓库在源代码中的"声明点"）
    decl = re.search(r"val\s+warehouse\s*=\s*state\.selectedWarehouse", body)
    assert decl and decl.start() < m_lines.start(), (
        "submitStocktake 校验顺序错误：必须先校验仓库，再校验 lines.isEmpty，"
        "与 submitInbound/submitOutbound 顺序保持一致"
    )


# ---------- T5: submitStocktake 函数体内必须存在对 warehouse.code 的引用 ----------
def test_t5_submitstocktake_uses_warehouse_code():
    """submitStocktake 必须把 warehouse.code 写入 StocktakeRequest，
    与 submitInbound/submitOutbound 模式一致"""
    src = _src(SCAN_VM)
    body = _extract_function_body(src, "submitStocktake")
    assert body, "submitStocktake 函数未找到"
    # 在 body 里 StocktakeRequest( ... ) 块内必须出现 warehouse.code
    m_req = re.search(r"StocktakeRequest\s*\(([^)]*)\)", body, re.DOTALL)
    assert m_req, "submitStocktake 内未找到 StocktakeRequest(...) 构造调用"
    req_body = m_req.group(1)
    assert "warehouse.code" in req_body, (
        "submitStocktake 的 StocktakeRequest( ... ) 必须传入 warehouse.code，"
        "与 submitInbound/submitOutbound 一致"
    )


# ---------- T6: 关键旧 BUG 标志：submitStocktake 之前无 selectedWarehouse 校验 ----------
def test_t6_no_submitstocktake_without_warehouse_validation_regression():
    """整段 ScanViewModel.kt 中，submitStocktake 函数体内必须存在至少一处 selectedWarehouse 引用。
    修复前整段零引用 → 修复后必须至少 1 处。"""
    src = _src(SCAN_VM)
    body = _extract_function_body(src, "submitStocktake")
    assert body, "submitStocktake 函数未找到"
    assert "selectedWarehouse" in body, (
        "submitStocktake 函数体内未引用 selectedWarehouse；"
        "审计报告 P1-A BUG 复现：盘点提交未校验仓库"
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
    print(f"\n所有 {len(tests)} 个 P1-A 回归测试通过")
