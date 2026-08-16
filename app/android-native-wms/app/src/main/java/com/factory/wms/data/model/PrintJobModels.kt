package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * 创建远程打印任务请求（对应后端 POST /print_queue/jobs）。
 *
 * 手机端提交入库/出库成功后，或物料档案详情页点"打印"时，调用该接口
 * 在打印队列生成一条任务，由桌面打印工作站（本地电脑）取走渲染出纸。
 * 注意：需先启动桌面打印工作站代理并保持 online，否则任务停留在 pending。
 */
data class PrintJobRequest(
    /** out_order / in_order / material_archive / label */
    @SerializedName("job_type") val jobType: String,
    /** 单据或物料主键 ID（label 类型为空）。 */
    @SerializedName("target_id") val targetId: Int? = null,
    /** label 类型：逗号分隔物料 ID 字符串。 */
    @SerializedName("target_ids") val targetIds: String? = null,
    val copies: Int = 1
)

/**
 * 创建打印任务响应（后端 /print_queue/jobs 返回）。
 */
data class PrintJobResult(
    @SerializedName("job_id") val jobId: Int? = null,
    @SerializedName("msg") val msg: String? = null
)
