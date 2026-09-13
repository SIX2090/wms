package com.factory.wms.data.model

data class DraftScanLine(
    val line: ScanLine,
    val name: String? = null,
    val spec: String? = null,
    val brand: String? = null
)

data class ScanEditDraft(
    val lines: List<DraftScanLine>,
    val warehouse: WarehouseDto?,
    val department: DepartmentDto?,
    val employee: EmployeeDto?,
    val contractNo: String,
    val requestId: String? = null,
    val inboundBusinessType: String = "采购入库",
    val selectedLocation: String? = null,
    val locationEnabled: Boolean? = null
    ,val evidence: List<String> = emptyList()
)
