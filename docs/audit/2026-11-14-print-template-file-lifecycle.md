# 2026-11-14 打印模板文件生命周期与备份隔离恢复

任务：PRINT-TEMPLATE-F01-FIX-FILE-LIFECYCLE-20261114-001；BUG-2026-11-14-007。

## 范围和生产边界

基线：3a4ac4c3fe8b5a74075f7c4407c5eab242321cac。工作区已有其他任务的修改/删除及未跟踪文件，均不纳入本批。只修改模板文件生命周期、测试静态目录、必要台账及Windows发行版本2026.11.55。

本轮不连接生产数据库，不 import 工作区应用，不探测业务接口、不操作账号/密码/单据，不重启/部署。仅核对8080监听及进程路径：PID8896，解释器位于既有独立发布目录。生产运行身份记录的backend为3652607ac6f381dd39e05e183c276dba443f508a、UI为afe8c9ad89d0d9bc408482ba88846a9b9133b307；不能把工作区新SHA冒充生产版本。

未清理/移动历史模板、数据库、WAL/SHM、日志、APK、runtime或wheelhouse，未执行gc/repack或历史重写。测试身份的文件权限只授予私有实验目录，IPv4/IPv6阻断规则仅匹配新建随机AppContainer SID，不改变生产网络。

## 已有备份恢复演练

只读取现有备份文件生成副本；SQLite连接仅针对副本/新恢复目标。复制已有恢复工具与只依赖标准库的runtime_guard，在仓库外运行，显式提供新的目标路径。

| 原备份 | 字节数 | 恢复结果 | 业务规模 |
|---|---:|---|---|
| app/backups/auto_startup_20261101_214924.db | 1232896 | 97张业务表结构与逐表记录摘要一致；integrity_check=ok，外键违规0 | 物料2、入库0、出库1、流水2；不能当作完整生产恢复点 |
| backups/before_frontend_20261023_7c25740a.db | 5361664 | 97张业务表结构与逐表记录摘要一致；integrity_check=ok，外键违规0 | 物料1356、仓库4、入库682、出库674、流水4159 |

原备份复制前后及演练后SHA256保持：启动备份7fc045c7ad9683c0b9c6b11ba2aaf6bd113d224290908bab9034153f67632335；业务备份6a04cd7afbf7dad5c50bdbeac048c42fa9165cb4c42b8654ac1b59ac58138f466。逐表只记录数量/摘要，不输出账号凭据或单据行内容。

这只证明所选旧备份能够由现有工具恢复，不证明当前生产的备份新鲜度、当前业务完整性、三账一致或新版本应用启动。默认C:\wms_backups为空不足以断言生产没有其他备份。

私有证据：%TEMP%/wms-space-safety-20261114-e766c045514b4e5fbd0222459caf9c80/{copy-manifest.json,restore-verification.json}；原备份及恢复副本均保留。

## 根因与实现

上传函数用UUID创建独立文件，这是合理的模板独立性，不能改成按用户文件名覆盖。真正缺口是数据库提交失败后文件仍存在、部分写入残片未回收，以及模板删除只删除记录。

统一回收函数按print_fill的实际路径解析，检查入库/出库/通用三类模型的全部引用（含静态URL、uploads相对路径及历史仅文件名形式）。只有当前static/uploads/print_templates目录内无引用的普通Excel文件才回收。内置builtin_、目录外/源模板、链接/多硬链接均保留；无法确认引用时保留。先提交数据库删除，再尝试回收；占用失败仅日志告警，保留已提交的正确返回。数据库删除失败则回滚，保留文件。

覆盖入库/出库新增、通用上传、在线新建复制、三个删除入口以及底层部分上传失败。编辑覆盖继续复用现有原子保存/重试，不改变模板选择、填充、下载、打印和角色权限。

pytest session静态目录拷贝至真实隔离profile临时目录，排除原uploads；个别测试的临时静态根覆盖仍可正常恢复。内置入库/出库副本跟随当前app.static_folder生成，相关两份测试读取实际静态根，保留原存在性、文件名和可填充断言。未批量删除原目录中的2212个文件。

## 本地验证与真实反证

源代码及运行时复制到新的私有目录，排除生产数据库、备份、上传、日志、凭据和Git目录。唯一LPAC身份、只读源码/解释器、仅私有数据目录可写、创建时分配Job、IPv4/IPv6精确SID阻断和父进程只读能力句柄均实际核验；不用内存URI或自述JSON代替隔离。

- 修前18模块：164 passed/18 warnings。
- 候选20模块：205 passed/43 warnings，其中新增37例、版式相邻4例；包含真实Flask路由/真实ORM/真实文件，不是伪造API返回。
- 精确恢复六份旧产品/测试源，保留新回归：22 failed/15对照passed，失败为文件残留等行为断言；恢复候选。未使用stash或撤销其他任务。
- 初始新用例的在线新建目标误用未注册in_order，400不能证明提交失败回收；已改为现有check并重新做完整候选/逆向验证，该无效红例不计最终证据。
- 最终23模块301 passed/43 warnings，包含台账CLI、分片分类、库存文档行号及CI文档分流契约；staged A1–A14 0违规、严格AI台账通过，git diff --check通过。完整HTTP冒烟和目标CI按用户授权另验。
- 完整verify_wms_bugs在新/旧源码均95 PASS、同一个AI-STAGE6-PRELAUNCH-001 FAIL，子进程隔离运行能力无效；不是本次新增失败，也不视为通过。现有安全阻断保持，交Linux隔离CI执行完整验证。

私有证据：%TEMP%/wms-template-validation-7n8zbla6/{baseline-164.log,combined-205-passed.log,rollback-final.log,quality-candidate.log,quality-baseline-supervisor.log,candidate.patch,workspace-unchanged.json}。每次父回执均记录Job归零、专属规则/Profile移除及受保护源码哈希不变。

## 验收顺序授权与交付状态

DEVELOPMENT_RULES.md §1.3原要求路由变更推送前完成隔离full_smoke_test.py；当前run_smoke_in_ci.py显式要求Linux隔离，Windows不满足。2026-11-14用户明确答复“允许本批由GitHub隔离CI验收完整冒烟”，允许本批先提交推送候选再验收完整冒烟/全站；没有授权部署、重启或生产数据操作，没有改项目永久规则或放宽脚本校验。

目标完整SHA、实际push和本目标WMS CI/WMS AI Verification/Android复用证明待回填。未完成目标验收前不称交付完成；即使代码CI通过，生产生效仍待人工确认。历史文件清理及Git维护不在本批执行。
