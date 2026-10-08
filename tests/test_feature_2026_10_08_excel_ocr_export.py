# -*- coding: utf-8 -*-
"""FEATURE-2026-10-08-EXCEL：送货单拍照 OCR 提取文字并导出 Excel。

静态契约测试（先写失败测试再实现，满足 A9）：
  1. 后端路由存在于 app/routes/ai_excel.py（A10：不进 app.py）
  2. 路由路径 /api/ai/document_ocr_excel + 权限装饰器与 document_ocr 一致
  3. 识别链路复用 _ai_call_llm_vision（不重复实现视觉调用）
  4. Excel 生成用 openpyxl Workbook；表头含单据类型/供应商/单据编号/日期/备注
     + 明细七列（物料编码/物料名称/规格型号/数量/单价/金额/单位）
  5. 返回 send_file + xlsx MIME + as_attachment
  6. blueprint 在 app.py 注册（ai_excel_bp）
  7. App 端四件套齐备：WmsApiService.documentOcrExcel（@Streaming）、
     WmsRepository.documentOcrExcel（JSON 错误识别 + 写入 Documents）、
     AiViewModel.exportOcrExcel、AiScreens「导出Excel」按钮 + FileProvider 打开
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ROUTE_PY = ROOT / "app" / "routes" / "ai_excel.py"
APP_PY = ROOT / "app" / "app.py"
API_KT = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms" / "data" / "api" / "WmsApiService.kt"
REPO_KT = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms" / "data" / "repository" / "WmsRepository.kt"
VM_KT = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms" / "ui" / "viewmodel" / "ai" / "AiViewModel.kt"
SCREEN_KT = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms" / "ui" / "screens" / "AiScreens.kt"
FILE_PATHS_XML = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "res" / "xml" / "file_paths.xml"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_route_module_exists():
    """A10：新路由必须在 app/routes/ 模块。"""
    assert ROUTE_PY.exists(), f"{ROUTE_PY} 不存在"
    body = _read(ROUTE_PY)
    assert "api/ai/document_ocr_excel" in body
    assert "ai_excel_bp = Blueprint" in body


def test_route_permission_and_chain():
    """权限与 document_ocr 一致；识别复用 _ai_call_llm_vision。"""
    body = _read(ROUTE_PY)
    assert "_web_or_api_role_required('warehouse', 'purchase')" in body
    assert "from app import (" in body or "_ai_call_llm_vision" in body
    assert "_ai_call_llm_vision" in body, "必须复用视觉调用链路"
    # 不做草稿创建（导出场景跳过建单）
    assert "_ai_create_draft_from_extracted" not in body


def test_excel_structure():
    """Excel 表头结构：头部信息 + 明细七列。"""
    body = _read(ROUTE_PY)
    assert "from openpyxl import Workbook" in body
    for col in ("物料编码", "物料名称", "规格型号", "数量", "单价", "金额", "单位"):
        assert col in body, f"缺少明细列：{col}"
    for head in ("单据类型", "供应商/客户", "单据编号", "日期", "备注"):
        assert head in body, f"缺少头部字段：{head}"
    assert "send_file" in body
    assert "spreadsheetml.sheet" in body
    assert "as_attachment=True" in body


def test_blueprint_registered_in_app():
    """blueprint 必须在 app.py 注册。"""
    body = _read(APP_PY)
    assert "from routes.ai_excel import ai_excel_bp" in body
    assert "app.register_blueprint(ai_excel_bp)" in body


def test_app_api_interface():
    """App 端 @Streaming 下载接口。"""
    body = _read(API_KT)
    assert "@Streaming" in body
    assert "api/ai/document_ocr_excel" in body
    assert "documentOcrExcel" in body


def test_app_repository_saves_to_documents():
    """Repository：JSON 错误识别 + 写入 Documents + MediaScanner。"""
    body = _read(REPO_KT)
    assert "suspend fun documentOcrExcel" in body
    assert "parseApiErrorMessage" in body
    assert "DIRECTORY_DOCUMENTS" in body
    assert "MediaScannerConnection" in body


def test_app_viewmodel_and_ui():
    """ViewModel 状态 + UI 导出按钮 + FileProvider 打开。"""
    vm = _read(VM_KT)
    assert "fun exportOcrExcel" in vm
    assert "isExportingExcel" in vm
    assert "excelExportedPath" in vm

    screen = _read(SCREEN_KT)
    assert "导出Excel" in screen
    assert "exportOcrExcel" in screen
    assert "openExportedExcel" in screen
    assert "FileProvider" in screen


def test_file_paths_supports_documents():
    """FileProvider 暴露 external-files-path Documents/。"""
    xml = _read(FILE_PATHS_XML)
    assert "external-files-path" in xml
    assert 'path="Documents/"' in xml


def test_api_document_ocr_excel():
    """A9 主测试：接口函数存在 + 路由注册 + 权限装饰器齐备。"""
    body = _read(ROUTE_PY)
    assert "def api_document_ocr_excel():" in body
    assert "api/ai/document_ocr_excel" in body


def test_decorator():
    """A9：本地权限装饰器存在（web session / Bearer 双通道）。"""
    body = _read(ROUTE_PY)
    assert "def _web_or_api_role_required(" in body
    assert "get_bearer_user" in body
