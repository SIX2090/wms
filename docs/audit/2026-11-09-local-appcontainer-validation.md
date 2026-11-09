# 2026-11-09：本机隔离应用回归证据

本记录只覆盖下述临时源码副本及明确列出的测试，不表示整批整改、通用测试启动器或 CI 已验收。

## 边界与源码

- 原工作区为 `C:\wms`，保留 main 和原有未提交内容。源码副本位于本次新建的 `C:\Users\Administrator\AppData\Local\Temp\wms-appcontainer-probe-92mofph3\source`。
- 只复制经 Git 文件清单筛选的代码／模板／规则等扩展名，共 2356 个文件、30500914 字节；排除 instance、backups、runtime、logs、uploads、outputs、虚拟环境等目录，不复制任何数据库或备份文件。所选路径逐层拒绝符号链接及重解析点。
- Python 3.11 解释器、标准库和已安装依赖复制至该临时目录，未安装全局依赖。用 `-I -S -B -X utf8` 启动，手动加入副本中的 site-packages，不执行 site／`.pth` 启动钩子。子进程环境从少量必要 Windows 路径重新构造，不继承业务凭据、数据库地址、Python 路径或 pytest 插件参数。
- 应用使用 `sqlite:///:memory:`；SQLite 文件探针只创建该任务目录内的新合成库。测试中的账号、密码、单据、库存及上传均属于隔离副本，未访问生产库、生产备份、生产日志、8080、真实业务服务、打印机或微信。

## 系统隔离探针

临时启动代码为同一任务目录内的 `probe.py`、`wfp_scope.py`，尚未作为通用入口纳入仓库。每次均创建唯一的 `wms.synthetic.<随机 UUID>` 身份：

1. 使用 Windows AppContainer，启用 ALL_APPLICATION_PACKAGES opt-out。进程内读取真实 token 的 AppContainer 标志和 `WIN://NOALLAPPPKG` 属性，不以环境布尔值或回执文件代替 token 核验；子进程重复探针。
2. 仅给该唯一身份授予任务副本的文件权限及所需兼容能力。普通目录外合成文件和另一个明确授予 ALL APPLICATION PACKAGES 读取权限的合成文件均被拒绝读取；不通过尝试打开生产库检验隔离。
3. 初始无网络能力的候选会阻止 Python `_overlapped` 导入，不能运行 SQLAlchemy。后续候选为该身份建立 IPv4／IPv6 ALE_AUTH_CONNECT 阻断规则，再允许框架创建系统套接字。提交规则前逐项反查过滤器的 layer、BLOCK action、恰好一个 package-SID 等值条件、准确 SID 和本次随机名称；禁止无条件规则。
4. 规则只匹配新建的测试身份。规则为非持久对象，但刻意不采用“父进程断开即自动删规则”的动态会话，避免监护进程崩溃后子进程网络放开。正常清理先终止并核对自有 Job 的 ActiveProcesses=0，再按准确 GUID／ID、名称和 SID 复核并删除本次规则；最后删除本次 AppContainer profile。不修改生产服务或 WMS 配置。
5. Job 约束整棵进程树、进程数、内存和界面／剪贴板访问；不继承其他进程句柄，仅显式传递任务自己的日志句柄。严格 Win32k 禁用候选不能加载 ctypes，已停止采用该不兼容组合。
6. 父进程持有新的随机高位回环监听器；测试进程和子进程无法建立连接，监听器未收到连接。私有内存 SQLite、任务内新文件 SQLite、任务目录写入成功，排除“所有操作都坏掉”的假隔离。

Windows API 的依据为微软 [AppContainer 启动说明](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer)、[token 信息](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class) 和 [WFP 过滤器结构](https://learn.microsoft.com/en-us/windows/win32/api/fwpmtypes/ns-fwpmtypes-fwpm_filter0)。具体运行结果以本机探针日志为准。

## 实际应用与盘点回归

通过上述探针后，实际导入副本的完整 `app.py`，在真实 Flask／SQLAlchemy 上核对 engine URL 和 `PRAGMA database_list`：私有内存库，无文件路径。

显式 pytest 清单包含以下 9 个文件，未使用空清单或扩大为任意命令：

- `test_bug_2026_09_06_001_check_uncounted_guard.py`
- `test_bug_2026_09_06_002_check_period_movement.py`
- `test_bug_2026_09_06_003_period_movement_import_layout.py`
- `test_bug_2026_09_13_004_check_row_identity.py`
- `test_bug_2026_09_13_005_check_area_totals.py`
- `test_check_add_category_generate.py`
- `test_inv_batch_001b_check_freeze_upsert.py`
- `test_inv_batch_001c_scan_hooks_batch.py`
- `test_round30_inventory_bounded.py`

修复前 50 项：19 failed、31 passed。保留数值／草稿／仓库断言、适配风险快照令牌，并新增旧 ORM 行残留用例后，中间候选仍有 7 个失败；只清 Session 又使旧登录缓存引用脱离 Session，产生 21 个失败，未合入该不完整候选。最终同时清理测试重建表之前的 Session 和 `_login_user` 缓存，并补充结构化风险计数，51 项全部通过（113 warnings，35.38 秒）。本次运行身份为 `wms.synthetic.ae54fc46f2844b11ae310e4e779d9ae2`；两条规则为 79619、79620，退出后已准确删除，profile 清理返回 0。警告没有被当作失败清零，也不代表警告问题全部解决。

对应日志保存在临时目录：`nine-files-baseline.log`、`contract-new-assertions-old-code.log`、`candidate-session-cache-failure.log`、`nine-files-candidate-passed.log`。共享工作区合入前逐文件核对原始 SHA-256，只复制实际验证的 11 个代码／测试文件，不复制整个副本或其运行期目录。

## 尚未覆盖

尚未完成通用启动器的伪造证明／异常退出／IPv6／链接并发替换等全面反例、全部应用测试、真实隔离 HTTP 冒烟、Android 构建、其他数据库方言和整批逆序回退。现有主动阻断的调度器及独立脚本仍保持阻断。这个本机候选不允许通过设置环境变量绕开这些入口，不允许将局部成功当作完整 CI 或生产生效。

## 扩大回归及只读文件入口（2026-11-09）

在以上 10 文件 57 项之后，扩展检查实际盘点路由、双仓扣减、库位迁移、三账只读核查和独立入口。28 文件首次运行有 21 failed、238 passed：10 项为库存权威文档的源码行号漂移，9 项为独立只读 CLI 仍被安全阻断，1 项为临时隔离环境缺少 Node，1 项为启动迁移测试继承 testing 配置而忽略自己的新文件库 URI。均保留原断言，分别同步真实行号、加入受约束的自有文件入口、复制私有 Node、在该新文件测试内显式选择原先所需的 production 配置；不修改生产配置。增加入口反例后，29 文件 312 项通过；再增加文件租约等安全反例后，29 文件 316 passed、208 warnings（117.06 秒）。这次身份为 `wms.synthetic.ff41ffa764224f1ba2bc4798ea485749`，专属规则 79633／79634 及 profile 正常清理。

`verify_inventory_identity.py` 只放行经过真实 Windows LPAC token 核验、属于本次 `wms.synthetic.<UUID>` 私有 profile 的普通合成文件。命令参数必须显式给出普通 SQLite URI，拒绝凭据／host／port／query／其他驱动，不继承默认库。读取路径必须位于操作系统返回的私有 profile；拒绝重解析点、符号链接、硬链接、设备路径、UNC、ADS 和路径别名。使用原生句柄固定文件和全部祖先目录，GENERIC_READ、仅 FILE_SHARE_READ，核对卷身份及打开路径，并在 SQLite `mode=ro`、`query_only` 读取和 JSON 对账期间保持句柄。链接或并发替换拒绝在建立 SQLite 连接之前完成。普通主机进程以及其他系统仍拒绝执行，缓存 app 的数据库 helper 仍阻断。

原生句柄候选先因最终路径查询模式不兼容而失败；改用同卷的已打开路径核验后，测试又发现只申请 READ_ATTRIBUTES 不能阻止并行写入。改为真正的 GENERIC_READ 后，写入、替换、父目录改名反例全部通过，未削弱断言。仅使用副本 README 构造越界／硬链接反例，无生产路径探测。只读核查原 66 项加上 4 个 URI authority／driver 反例共 70 项通过；这 4 个反例在旧 URI 检查下实测失败，新检查下通过。该 70 项包含在上述范围内，不能与 316 简单相加。

证据日志位于本任务临时目录的 `adjacent-28-files-baseline.log`、`lease-final-path-failed.log`、`readonly-66-passed.log`、`29-files-316-passed.log`、`readonly-70-passed.log`。通用调度器、浏览器及缓存应用 helper 的阻断仍保留；这个受限 CLI 不意味着所有测试入口已恢复。

## 迁移持久化与双连接写锁（2026-11-09）

完整迁移函数的 34 项合成内存回归原有 2 项持久化失败。新检查点在既有外层 BEGIN EXCLUSIVE 内使用嵌套 SAVEPOINT，保留写锁并撤回未标记业务 DML 后仅保存经验证的新增空表和索引；捕获重建失败时保留旧 no-commit 行为。新增 9 项检查点测试包括双连接文件测试，DELETE／WAL 两种模式下重放前的第二写入均收到 SQLITE_BUSY，原业务值保持。所有文件都由真实 token 对应的私有 profile 新建，不使用生产 schema 或记录。

第一次将全部测试放进一个进程的 31 文件运行是 44 failed、319 passed：10 个文档行号漂移断言未同步，34 个完整迁移用例在解析 app.py 时因先前应用测试占用而触及 512 MiB 进程内存上限。保留 `31-files-memory-and-doc-failed.log`；同步文档定位后改用两个全新进程，保持相同非空用例集合及原内存限制。迁移与检查点两文件实际为 43 passed、32 subtests passed，47.07 秒，见 `migration-43-passed.log`。身份 `wms.synthetic.3ffa802797e74d9da6184ff155200966` 的规则 79648／79649 及 profile 均正常清理。另一 29 文件的本轮结果另记，不将尚未完成的运行预填为成功。

组件逆向对照在本次新建的临时合成 Git main 仓库 `wms-schema-checkpoint-rollback-v6si80d_`：候选版本两项持久化断言通过，revert 本次候选提交后两项重新失败，旧 app.py 哈希精确恢复。此举没有修改共享工作区的 Git 历史，也不是整批回退验收。没有执行生产迁移或重启服务。

29 文件最新复验：**320 passed、208 warnings，124.05 秒**，包含新增的 4 个 URI 反例；见 `29-files-320-passed.log`。身份 `wms.synthetic.3ed4732991c646b6a09a88a1cd2a2c05` 的规则 79650／79651 及 profile 正常清理。与迁移 43 项为互不重叠的测试文件，共 363 项通过；不是全站或完整 CI。

## 自动更新与合成备份补证（2026-11-09）

用户已明确批准：有已跟踪未提交改动就保留现场、跳过自动更新。main 不再自动 stash／apply／pop，旧 stash 配置不能启用；干净工作区备份成功后重检，期间新编辑或状态查询失败也停止。合成 Git 的暂存／未暂存／未跟踪文件、其他 stash、并行写入、失败／超时／HEAD 变化和备份期间变更两组分别 10／12 项通过；这些 Git 仓库均为本轮新建、仅 file 协议、禁全局配置与钩子，未对 C:\wms 运行变更 Git 命令。

进一步实际运行合成备份和受限子进程的 8 项，先有 2 failed／6 passed。DEVNULL 全局设备在 LPAC 中被拒，测试子进程改用独立新空文件提供相同 EOF，保留 runner 传 DEVNULL 及真实 timeout 断言，子进程加 -I -S -B；复验仍有 1 failed／7 passed。保留诊断后确认，源合成库可读，但 strict 路径解析需要被 LPAC 拒绝的额外 DOS 映射权限。快照 helper 改用绝对文件 URI、stat 存在性及 mode=ro，源／目标身份与原子发布保护不变。加入完整快照发布用例和缺失源保留断言后，3 文件 30 passed（5.58 秒），包括 WAL、硬链接、源不被修改、旧备份保持、损坏和中途失败。

本次身份 `wms.synthetic.3784f429a67944b6a57fa7a02d370279` 的专属规则 79670／79671 及 profile 正常清理。组件合成 Git 逆向回退恢复旧快照 helper 的精确哈希后，原合成备份再次 1 failed／3 passed。日志为 `auto-backup-and-child-first-failed.log`、`auto-backup-resolve-denied.log`、`synthetic-backup-30-passed.log`、`snapshot-after-inverse-failed.log`。这不是生产备份演练或通用隔离入口完成证明。

## 后续隔离加固与重新验证（2026-11-09）

后续审查确认：早期临时启动器给测试身份整个任务根目录写权限，未充分证明源码、解释器和监督器不可篡改；旧解释器副本还出现文件缺失，原因未确定。没有把旧副本继续当成可信运行环境，也没有把早期回执当作不可篡改证明。上述旧功能结果保留，但隔离强度应以本节新证据为准。

重新建立任务根目录 C:\Users\Administrator\AppData\Local\Temp\wms-restricted-validation-66i0081z，从已安装解释器重新复制干净运行时和代码。排除生产 instance、数据库、备份、上传、日志、构建、凭据等目录或文件，只复制代码／测试／文档；app 导入需要的 backups 路径仅由父进程创建新的空只读目录，没有复制备份。

- 每次新建独立 LPAC 身份；根目录、源码、清单、解释器和启动器只授予 RX，只有本次 data／logs／uploads 及真实 token 对应的新 profile 可写。原生探针检查受保护文件及目录的写、删除和 WRITE_DAC 均被拒，目录外普通与 ALL APPLICATION PACKAGES 合成 canary 均不可读。
- 两条 IPv4／IPv6 WFP 阻断规则在进程创建前安装并反查，恰好匹配本次新 package SID；不依赖子进程自觉禁网。以自有随机高位回环 canary 验证无法连接，不访问生产地址。规则不是动态会话，监督器异常退出不会直接使子进程网络放开。
- 使用 PROC_THREAD_ATTRIBUTE_JOB_LIST 在创建时分配唯一命名的自有 Job，恢复线程前再核验实际成员资格，避免先创建后补分配的窗口。进程数、内存、界面限制及 kill-on-close 保持，不允许 breakaway。
- 父进程状态存于根目录外 C:\Users\Administrator\AppData\Local\Temp\wms-supervisor-state-gw97lfxe，子进程不能读写。恢复执行前原子新建 assigned 记录，保存准确身份、PID、Job 名、过滤器 ID／GUID 和关键文件哈希；正常结束先终止并验证该 Job 活跃进程数为零，再移除准确的自有过滤器与 profile，最后原子记录 closed、退出码和哈希不变。会话中断后可以读取该父进程回执核实结果，不根据旧 PID 猜测归属或结束其他 Python。
- 子进程先用真实 token 重复隔离探针，再以 -I -S -B 和明确非空、无重复的测试文件清单启动 pytest。DATABASE_URL／WMS_DATABASE_URI 仅为 sqlite:///:memory:，应用日志、上传、secret 和合成账号均为本次测试值；不加载用户 .pth 或自动发现外部 pytest 插件。文件库证明使用 mkstemp 创建，不复用 PID 文件名。

只读源码初次暴露 pytest 默认缓存目录写入问题：两个负例运行已到测试结尾但未退出，均只通过准确命名 Job／成员核验终止自有树，退出 143；不计通过，规则和 profile 正常清理。保留 cacheprovider，将 cache_dir 明确放到经过真实 token 校验的私有 profile/Temp，其他断言与内存／权限限制保持，后续负例正常结束。旧候选有一次完整运行被用户消息打断，缺少最终结果，也未计通过。

当前重新验证的采购和网页结果：30 个明确文件 935 passed / 70 warnings；扩大同类点后 14 文件 587 passed / 12 warnings，清单重叠不相加；13 产品文件精确逆向对照 32 failed / 76 passed。首次负金额测试把现有错误码写成 200，纠正为原有 400 后，旧源码 5 failed / 6 passed，负总额保护保留。详情、日志与组件回退见金额专项。Windows 原生隔离探针九项在上述运行均为真。

935 项身份 wms.synthetic.965ddf929951458ca7b60b54536b18ab、逆向身份 wms.synthetic.8a01ddffee9e451e87877a08fd164e22、最终 587 项身份 wms.synthetic.91f0534eba5a40d8865714f18519d608 的父进程回执均为 closed，Job 归零、专属过滤器和 profile 已移除、受保护文件哈希不变。

此启动器仍为本机临时 Windows 验证工具，未作为通用、跨平台或 CI 安全入口交付。既有 smoke／verify／浏览器入口无法证明隔离时的 fail-closed 保持；没有放宽生产端口、伪造 isolation-file 或恢复未知数据库访问。完整 CI、整批验证及生产生效仍未完成。
