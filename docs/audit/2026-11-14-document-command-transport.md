# 复制及来源下推的网页请求意图（Node VM 专项）

固定产品基线38b5440c。只扩展现有api.js的12个实际新单命令URL（9复制、采购选单/按单下推、BOM转领料），仍沿同一pendingDocumentKeys和X-Idempotency-Key协议。命令body里的id/order_id是来源身份，不能套编辑跳过；没有body的复制也需key。数据仅在documentRequestKey局部置空用于意图识别，真实请求body已先构造并完整保留。

原20保存路径、其编辑跳过、preview号键生成及清除行为保持字节相同。本专项不把原preview-cache源码观察宣称真实UI故障。命令用完整URL意图，未知响应/网络/JSON解析/HTTP/业务失败保留key，已知success后由原URL清除逻辑释放，下一次人工命令分配新key。显式调用方header、CSRF、same-origin credentials、JSON和FormData不变；不同源URL分开，不增加业务审批或状态。

141明确非空方法直接运行真实api.js到Node VM，传输全部由闭合fake fetch提供，无浏览器/真实服务器/数据库。12URL×8失败/正文/显式header模式，20旧保存、20编辑、5非命令对照；子Node只允许标准环境白名单，去掉继承NODE_OPTIONS/NODE_PATH/DB目标，并提前预载网络/child_process/worker_threads拒绝器。

旧源/新源方法和断言相同，旧应84断言失败/57正常对照/0初始化错误，新141绿。精确结果、3文件私有Git逆序回退及LF哈希见frontend-proof.json；根任务另做完整后端+前端整批R8和新SHA CI。源码VM不是实际浏览器。生产数据库/备份/账号/服务未触碰；生效确认：待人工确认。

## 活跃采购选单页面入口追加

完整12调用链检索发现in_order_add.html的createInOrderFromPurchaseOrderSelection仍裸fetch，绕过统一api.js，因此仅给api补命令key不够。只把它接到WMS.api.postRaw，保原选择/数量/上限校验、warehouse_id/remark/items payload、成功跳转和中文报错。其余活跃复制/下推均已走api.post/postRaw；禁用历史bom_detail不恢复。

独立20个Node VM实例：12真实postRaw命令响应丢失/同key重试/成功后新key，另8个真实模板函数的空选、零、非数、超量、成功、网络、业务/HTTP错误。旧模板同20应4断言失败/16正常对照/0初始化错误，新20通过；恢复候选后141+20共161 VM检查通过，与已有59相邻分开报告。

本追加为模板变更，生产需重启 WMS 服务生效；本任务没有重启、部署或访问生产。组件3文件独立Git逆序/恢复与最终whole批R8分别核对。生效确认：待人工确认。
