package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/** 移动端合同选项（出库单等选填合同字段的快速匹配）。
 * 对应服务端 GET /api/mobile/contracts 的 data.items 元素。 */
data class ContractDto(
    val id: Int?,
    @SerializedName("contract_no") val contractNo: String?,
    @SerializedName("project_name") val projectName: String?
)

/** 合同搜索响应（data.items）。 */
data class ContractsListData(
    val items: List<ContractDto> = emptyList()
)
