# -*- coding: utf-8 -*-
"""领料部门/领料人下拉（2026-09-12 用户需求）Android 锚点。

需求：扫码出库界面增加「领料部门」「领料人」两个下拉，选部门后员工列表联动过滤。

断言 Android 五层（model/api/repository/viewmodel/ui）都接入：
- DepartmentDto/EmployeeDto/DepartmentsListData/EmployeesListData 存在
- OutboundRequest 带 department_id / picker
- Retrofit @GET api/departments 与 api/employees（?department_id= 过滤）
- Repository getDepartments / getEmployees
- ViewModel departments/employees/selectedDepartment/selectedEmployee 四个状态
  与 loadDepartments/loadEmployees/selectDepartment/selectEmployee，
  submitOutbound 从 state 取 departmentId/picker（不再由 UI 传文本）
- UI 两张 PartySelectorCard + 两个 PartyPickerDialog + 确认弹窗回显
- 版本递增 versionCode ≥ 12 / versionName ≥ 3.7.1（AI-MOB 发版递增；
  3.7.2 为首页概览下钻，本文件不锁具体版本号）
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"
GRADLE = ROOT / "app" / "android-native-wms" / "app" / "build.gradle.kts"


def _p(rel: str) -> str:
    return (BASE / rel).read_text(encoding="utf-8")


def _version_code(gradle: str) -> int:
    """versionCode 取整数，便于断言 >= 而非锁死某个具体值。"""
    m = re.search(r"versionCode\s*=\s*(\d+)", gradle)
    assert m, "build.gradle.kts 未找到 versionCode"
    return int(m.group(1))


def _version_tuple(gradle: str) -> tuple:
    m = re.search(r'versionName\s*=\s*"([\d.]+)"', gradle)
    assert m, "build.gradle.kts 未找到 versionName"
    return tuple(int(x) for x in m.group(1).split("."))


def test_model_dtos_and_request_fields():
    src = _p("data/model/DepartmentModels.kt")
    assert "data class DepartmentDto" in src
    assert "data class EmployeeDto" in src
    assert "data class DepartmentsListData" in src
    assert "data class EmployeesListData" in src
    assert '@SerializedName("department_id") val departmentId: Long? = null' in src

    req = _p("data/model/ScanRequests.kt")
    assert '@SerializedName("department_id") val departmentId: Long? = null' in req, \
        "OutboundRequest 必须带 department_id（后端写 OutOrder.department_id）"
    assert "val picker: String? = null" in req
    # 旧字段保留：未升级的调用方与后端文本兜底仍可用
    assert "val receiver: String? = null" in req
    assert "val department: String? = null" in req


def test_api_endpoints():
    src = _p("data/api/WmsApiService.kt")
    assert '@GET("api/departments")' in src
    assert "suspend fun getDepartments()" in src
    assert '@GET("api/employees")' in src
    assert '@Query("department_id") departmentId: Long? = null' in src


def test_repository_loaders():
    src = _p("data/repository/WmsRepository.kt")
    assert "suspend fun getDepartments(): Result<List<DepartmentDto>>" in src
    assert "suspend fun getEmployees(departmentId: Long? = null): Result<List<EmployeeDto>>" in src


def test_viewmodel_state_and_actions():
    src = _p("ui/viewmodel/scan/ScanViewModel.kt")
    assert "val departments: List<DepartmentDto> = emptyList()" in src
    assert "val employees: List<EmployeeDto> = emptyList()" in src
    assert "val selectedDepartment: DepartmentDto? = null" in src
    assert "val selectedEmployee: EmployeeDto? = null" in src
    assert "fun loadDepartments()" in src
    assert "fun loadEmployees()" in src
    assert "fun selectDepartment(department: DepartmentDto?)" in src
    assert "fun selectEmployee(employee: EmployeeDto?)" in src
    # 选部门后联动刷新员工列表（含清除选择的情况）
    assert "repository.getEmployees(_uiState.value.selectedDepartment?.id)" in src
    # 提交从 state 取值，不再依赖 UI 传入的 receiver/department 文本
    assert "fun submitOutbound() {" in src
    assert "department = state.selectedDepartment?.name" in src
    assert "departmentId = state.selectedDepartment?.id" in src
    assert "picker = state.selectedEmployee?.name" in src


def test_screen_cards_dialogs_and_confirm():
    src = _p("ui/screens/ScanScreens.kt")
    assert "PartySelectorCard(" in src
    assert "PartyPickerDialog(" in src
    assert "showDepartmentDialog" in src
    assert "showEmployeeDialog" in src
    assert "领料部门（选填）" in src
    assert "领料人（选填）" in src
    # 进入出库页自动加载两个下拉数据
    assert "viewModel.loadDepartments()" in src
    assert "viewModel.loadEmployees()" in src
    # 确认弹窗回显所选部门/领料人
    assert "领料部门：" in src
    assert "领料人：" in src


def test_party_picker_component():
    src = _p("ui/components/PartyPicker.kt")
    assert "fun PartySelectorCard(" in src
    assert "fun PartyPickerDialog(" in src
    assert "data class PartyPickerItem(" in src
    # 允许清空（两个字段都是选填）
    assert "allowClear: Boolean = true" in src


def test_version_bump():
    gradle = GRADLE.read_text(encoding="utf-8")
    assert _version_code(gradle) >= 12
    assert _version_tuple(gradle) >= (3, 7, 1)
