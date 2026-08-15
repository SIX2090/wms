package com.factory.wms.data.model

data class SubmitResult(
    /** 单据主键 ID（用于提交后"打印单据"调用 /print_queue/jobs 的 target_id）。 */
    val id: Int? = null,
    val order_no: String?,
    val check_no: String?
)