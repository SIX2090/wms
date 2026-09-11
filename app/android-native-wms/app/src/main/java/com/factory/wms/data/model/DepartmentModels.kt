package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * 部门（2026-09-12 扫码出库「领料部门」下拉数据源）。
 * GET /api/departments data.items 元素。
 */
data class DepartmentDto(
    val id: Long,
    val code: String? = null,
    val name: String? = null
)

/** GET /api/departments 响应（data.items）。 */
data class DepartmentsListData(
    val items: List<DepartmentDto> = emptyList()
)

/**
 * 员工（2026-09-12 扫码出库「领料人」下拉数据源）。
 * GET /api/employees[?department_id=] data.items 元素。
 */
data class EmployeeDto(
    val id: Long,
    val code: String? = null,
    val name: String? = null,
    val position: String? = null,
    @SerializedName("department_id") val departmentId: Long? = null,
    @SerializedName("department_name") val departmentName: String? = null
)

/** GET /api/employees 响应（data.items）。 */
data class EmployeesListData(
    val items: List<EmployeeDto> = emptyList()
)
