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
    /** 入库供应商（BUG-2026-09-18-008）：与 contractNo 同样属于"用户已填但还没提交"的单头数据，
     *  进程被回收后必须一起恢复，否则断点续传会静默丢掉供应商关联。 */
    ,val supplier: SupplierDto? = null
    ,val inboundRemark: String = ""
)
