# BUG-2026-11-08-010：有限下推 TCP 诊断及验收

**最终状态（2026-11-14）**：精确6d22ea2a的完整CI、真实1/25行TCP两例及Windows50包均已验收；生产生效待人工确认。

固定源码基线57df192705a37b593ef0e1a3690a01e2f126ee72。新增一个有限入口，不改旧LIVE脚本、生产服务、公共性能/冒烟框架或业务代码。未使用现有账号、单号、数据库或备份，也未在宿主导入/收集/运行WMS或发HTTP。

## 原能力及本次缺口

现有diagnose_synthetic_push.py提供实际七阶段业务和库存/唯一草稿断言，但transport明确是flask-test-client。perf_baseline.py的OwnedPerfHTTP已提供真实TCP与隔离监听，不过场景是有限读取，不含保存→完成→来源详情→下推页→下推→重放→目标详情的写入诊断。本候选只补这条已在能力清单登记的TCP缺口，不把所有34旧诊断入口恢复或010全部完成。

## 安全复用与协议

scripts/diagnose_synthetic_push_tcp.py只接受--scenario inbound-push-tcp和--rows 1/25，无URL、DB、凭据、真实ID或输出文件参数。先验证现有Linux真实内核边界及新建字面内存库，再复用initialize_synthetic_app和OwnedPerfHTTP。每次请求由既有IsolatedSession核验连续持有的高位回环socket、nonce及相同origin；拒绝代理和自动重定向。新入口不建立第二套监听或客户端，也不读取任意身份JSON来假装所有权。

HTTP helper本身也在传输前独立require_runtime；只接收本次OwnedPerfHTTP及其sessions中的真实IsolatedSession，核同lease/identity/base URL/nonce、线程存活和实时lease.validate。不能仅绕过diagnose后给helper普通requests.Session和旧服务地址。宿主合法相对路径配fake组件也必须先拒绝，源码检查不patch内核guard为恒真。

现有只读性能初始化器关闭CSRF，本写入场景明确恢复WTF_CSRF_ENABLED=True。通过真实登录页面CSRF、合成账号登录及认证API确认会话；从真实业务页面获取CSRF和单据revision。缺CSRF POST必须400且没有新单；伪造revision完成请求必须409且库存不变；之后真实版本请求才能完成入库。原权限、Pydantic、状态、签名、DocumentPushLine请求ID与锁均保留，不使用force代替盘点风险确认，本场景只沿既有入库完成参数。

只有新内存库自造两仓、物料、单位、供应商和账号。七个业务阶段输出实际HTTP状态和毫秒；额外两次页面协议读取、三步认证和两个拒绝请求分别列出实测耗时，总耗时包括初始化、所有HTTP及清理，不能把前置请求隐入七阶段总和。详情复用已验_detail_content，按真实标题及业务表格行确认当前合成单据/物料，不以HTML字符串或空壳200冒充成功。

完成后的全局/A仓数量均为行数×2，B仓始终0；下推仅生成一个pending OutOrder，行数和数量各为场景行数；相同请求ID重放返回相同目标，真实DocumentPushLine每来源行只关联该目标，库存全程不被草稿消耗。离开既有OwnedPerfHTTP上下文后必须证明线程已停、监听fd已关闭才返回成功报告。报告不含用户名、密码、nonce、base URL、请求头、payload或页面正文。

## 验证与交付边界

以下保留候选阶段的本机验证记录；最终精确目标证据见文末。

本机只执行显式8项标准库unittest源/拒绝检查及2个实际未授权子进程拒绝对照，包含真实HTML令牌读取、未知参数、错误method/跨源相对目标写前拒绝、普通会话合法路径仍拒绝、禁止自动重定向和能力/清理结构。源码不使用fake正向HTTP结果替代真实TCP证据。源测试类为真实unittest.TestCase，另有独立零参数pytest拒绝测试；封闭pytest实际收集/执行由主任务对固定文件验证，不能只数AST方法。

tests/test_synthetic_push_tcp_runtime_20261114.py有2个显式参数实例（1行/25行），首先require_isolated_test_runtime，再在Linux真实边界启动自有CLI子进程，逐项验收七业务阶段、两协议读取、认证、CSRF/revision拒绝、数量/唯一草稿/重放/仓隔离、精确source SHA、清理及不泄漏能力值。没有在宿主collect/run，不预填这些真实TCP已通过。

候选四新增文件在自有Git文本副本整批逆序回退、逐字节恢复基线和候选。旧版失败证据是明确缺少有限TCP诊断入口的能力断言，不是模糊依赖缺失/初始化错误，更不是声称旧业务下推失败。全部结果和LF补丁/精确文件hash见伴随tcp-diagnostic-final-proof.json；实际精确SHA Linux CI仍由主任务验收。

生效确认：待人工确认。无生产部署、重启、配置或迁移操作；不代表所有其他诊断、物理设备或其他数据库验收完成。


**2026-11-14有限TCP精确验收：代码、CI和包分别确认。**

- 最终代码 `6d22ea2a020f137311e42f3178e14e25dd34c5a2`（Windows2026.11.50）已普通push，实际输出 `95a5d02c..6d22ea2a main -> main`，退出0并反查远端完整SHA一致；没有跳过钩子或force。6文件整批逆序回退/恢复覆盖2523基线源码blob，整树/逐文件一致；5静态门禁、5相邻组、9真实封闭源码pytest/23子测试通过。
- [WMS CI43556101954](https://github.com/SIX2090/wms/actions/runs/43556101954)、[AI43556101983](https://github.com/SIX2090/wms/actions/runs/43556101983)、[性能43556102055](https://github.com/SIX2090/wms/actions/runs/43556102055)均completed/success；所有unit、静态、4verify、smoke、browser、gate成功。unit5958+5662+4731=16351通过，203跳过，1584子测试通过；较前批新增9源码+2真实TCP=11测试、23子断言，跳过数未增加。
- 新增 `test_synthetic_push_tcp_runtime_20261114.py` 的1/25行两例属于分片2、没有skip分支/跳过夹具，随该精确目标标准Linux隔离完整运行。每例七业务阶段、三认证、两协议读取、两安全拒绝均记录实际状态/时间；严格验证CSRF400、伪造revision409、来源/目标详情真实行、同请求重放唯一草稿、双仓库存不变和自有监听/线程关闭。宿主未import/collect/run完整WMS或发TCP请求，源码测试不充当真实TCP证据。
- [Windows43556841082](https://github.com/SIX2090/wms/actions/runs/43556841082) completed/success，日志实际 `built_verified`；[windows-v2026.11.50](https://github.com/SIX2090/wms/releases/tag/windows-v2026.11.50) 已发布并绑定完整6d目标，四资产齐全。ZIP 97267685字节，SHA256 `45c9805ccb50db049500f5f76e6a64a376c968227c5db3dabd9b5bed7e32febf`。Android成功祖先 `aa982156adb5007581775490ebbe32825024e5d4` /43548469707 的39/3.9.15与相关工作流路径到6d零差异；未声称重新构建APK或现场安装。
- 010仅增加并验收这一有限TCP能力，旧34危险入口继续拒绝；独立锁时序、额外CRUD/菜单/截图等历史能力须按真实需要选择，未将17/34历史分类宣称全部恢复。006代码57及Windows49的已验收历史保留，当前不再有本批已知失败未处理；不保证整个WMS没有潜在缺陷。
- 没有生产数据库/备份、真实账号/业务单据、现役服务、微信/打印、部署/重启或迁移操作。代码、CI与包已验收，生产生效仍待人工确认；原两删除/两未跟踪工作保留。生效确认：待人工确认。
