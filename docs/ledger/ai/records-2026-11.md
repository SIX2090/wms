# 2026-11 开发记录

### PRINT-TEMPLATE-F01-FIX-FILE-LIFECYCLE-20261114-001：既有打印模板文件生命周期子修复

- 状态：代码目标35edea5f227084105b0dd1b16f60dfad88eab76c已实际push并通过完整CI；生产未部署，文档收口另验。关联BUG-2026-11-14-007，父任务PRINT-TEMPLATE-F01/F04。
- 范围：三类模板删除后引用核对、创建/部分写入失败回收、pytest静态文件隔离。保留独立模板、内置模板、共享文件和原权限；不新增AI能力、路由、模型或配置。
- 验证：修前164 passed；20模块205 passed/43 warnings；旧代码22 failed/15对照passed，规则0违规；最终23模块301 passed/43 warnings、严格AI台账通过。Windows完整verify的新旧共同隔离能力失败已留证，不计通过；用户授权完整冒烟/全站交本批GitHub Linux隔离CI，提交钩子保持。
- 备份：现有备份隔离恢复及97表逐表比对通过；现有旧业务备份不能证明当前恢复点。本轮不连接生产数据库，不重启、不部署、不批量清理历史文件。
- CI：WMS43581392135、AI43581392093成功；16407 passed/203 skipped/1636子案例，完整HTTP122/122。Android成功祖先0d1f7989的43574253341输入不变；未把本地共同隔离失败当通过。
- 证据：[专项记录](../../audit/2026-11-14-print-template-file-lifecycle.md)。生效确认：待人工确认。

### MOBILE-UPDATE-20261114-001：Android App 自动更新

- 状态：代码及CI交付完成，稳定42/3.9.18已发布；真实手机尚未安装，设备生效待人工确认。
- 本阶段授权：建立并备份长期固定签名；将私钥及密码保存到 SIX2090/wms 的 Actions Secret WMS_MOBILE_SIGNING_BUNDLE，GitHub 已确认保存。新包名 com.factory.wms.mobile / WMS 手机端；旧 App 本地数据保留且不自动迁移。
- 原始授权：2026-11-14 用户附件允许实现、隔离验证和提交验收，禁止缺密钥临时换签名、卸载清数据或操作生产。
- 前一阶段实现目标：fd56b6dd947971ff6998b6fbf6cf2f745988ba25，Android 189项测试与lint成功，但固定签名Secret为空导致出包被拒；AI验证成功，整体不算验收。
- 查重：签名配置归既有 BUG-2026-09-04-003，不重复登记 BUG；服务器 Git 更新和手机自更新不同。
- 回退：cf0bc750、b2fe2fbf、7cea3cb8，完整树与349850df基线一致；随后只登记事项并前移Windows发行版本52。
- 回退验收：4d9e4f86e32e9be22347ddfe2f410e00604157e7 已实际正常push，Android43567672542、WMS43567672637、AI43567672566均completed/success；只证明原基线恢复，自动更新仍待原签名。两份Markdown收口自身CI另验。
- 纠正验收：0d1f798930e336c8b3ab055e2855047fa5e7d45c实际正常push，Android43574253341、WMS43574253315、AI43574253316全部success；稳定提升43574863365成功生成android-mobile-stable-v42-0d1f798930e336c8b3ab055e2855047fa5e7d45c。远端189项Android测试通过，独立APK下载/哈希/正式签名/包名版本核验通过。Android42/3.9.18，Windows2026.11.54。本次两份Markdown收口自身CI另验。
- 证据：[专项记录](../../audit/2026-11-14-android-app-update.md)。生效确认：未安装，待人工设备验收；生产、密码与真实手机未操作。
