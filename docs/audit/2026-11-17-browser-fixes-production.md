# 浏览器缺陷修复生产部署（2026-11-17）

## 发布结果

- 2026-11-17 15:04（北京时间）已通过原 `WMS-Warehouse` 计划任务完成切换。
  正式运行版本 **2026.11.87**，后台和页面来源均为
  `813f9cc382910613ee4f5899a078313c89eb4121`，唯一8080监听PID为5856。
  15:03:40停止原业务实例，15:04:20完成新实例被动身份核对，窗口约40秒。
- 发布范围：已验收的 BUG-2026-11-17-001～007；前五项见
  [浏览器确认缺陷](2026-11-17-browser-confirmed-bugfixes.md)，后两项及
  O-01～O-05判断见[观察项复核](2026-11-17-browser-observations-recheck.md)。
  这五个观察项不是五个产品缺陷；O-04复验中另确认并修复两项实际缺陷。
- 使用封存目录 `C:\wms_releases\20261117_browser_fixes_813f9cc3`，
  不从共享开发目录启动，不包含后续仓库月报目标fe387b362或未提交Android改动。
  制品ID：`d97d7aea111d13f7f0a8cb1c1873197249d6a8c9a0973102c3f31a8818b1955a`。

## 授权和数据边界

- 用户明确授权部署，并在本次询问中答复“允许预检和正常启动访问原库”。
  仅沿既有受保护入口预检和正常启动；未执行迁移、初始化、回填、恢复、
  数据库复制、账号修改、测试单据或生产HTTP测试，没有安装APK。
- 启动保护保留，预检exit0、read_only_startup=true、schema_check=passed、
  listener_started=false；程序模型、配置和requirements没有变化，原启动顶层
  语句不变，受保护入口仅更新固定源码SHA。配置指纹与原实例一致：
  `864e66e6526f80ce95748b3f1fe6ea7f7a7bce200414abb08204471283a090da`。
- 六个既有持久目录只建立相同目标的目录联接，未复制或扫描业务内容。
  原任务注册、监护入口及max-restarts保持；任务只启动一次，监护计数仍为1，
  未执行预算重置。正常运行配置与既有外部任务状态保持，不主动触发外部发送。

## 并行发布协调及回退

- 准备期间另一任务上线扫描线修复`64e3a503129073e41101351525ce6b59fc374754`。
  首次切换检查因原动作文件hash变化而安全中止，尚未停止服务或替换动作。
  待该任务已完成切换、实例稳定超过300秒后，以新现役制品重新建立回退基线。
- 本目标包含该扫描线修复；保留刚上线的Android构建903下载包，SHA256为
  `e63d0de98633e452bc77d03aa7dd582d6c533837b5a3d95aa6d8edb2d42dc77b`，
  没有回退到准备阶段的旧902包。
- 完整回退目录为 `C:\wms_releases\20261117_h5_scanline_64e3a503`，
  制品ID `4e23e16a85ced529019106a84dbe446b339027ceb1e4a77d71b757cf1cc42630`。
  私有程序选择指针完成候选→旧制品→候选三段校验，不冒充生产服务回退演练。
  上线后新旧各7474个封存程序文件全量hash校验通过；原动作的原子替换备份保留。
  回退只回完整程序组合，不恢复数据库、不回滚业务记录。

## 验收证据和限制

- 已部署目标的[WMS CI](https://github.com/SIX2090/wms/actions/runs/44029836507)、
  [WMS AI Verification](https://github.com/SIX2090/wms/actions/runs/44029836526)、
  [Windows Portable Release](https://github.com/SIX2090/wms/actions/runs/44029985627)
  均为completed/success。Android目标因路径过滤无运行；另核验成功祖先
  `64e3a503129073e41101351525ce6b59fc374754` 的
  [Android APK Build 903](https://github.com/SIX2090/wms/actions/runs/43999372845)，
  祖先关系退出0，祖先至部署目标的Android和构建工作流输入差异为空。
- 合成Chrome及246项模块/相邻回归结果沿用已验收记录，没有在生产重做测试。
  上线实测的是启动保护、程序完整性和进程/任务/页面来源身份；监听成功不等于
  业务、库存、打印、AI或手机体验已实测。真实硬件及用户正常使用反馈待确认。
- 本轮本机证据目录：`C:\wms_test_tmp\deploy-observations-20261117`，含
  `normal-startup-approval.json`、`rebase-current64-proof.json`、
  `protected-preflight-result.json`、`cutover-result.json`、
  `postverify-result.json`及`release-ci-proof.json`。未将原始日志或配置秘密提交仓库。
- 本部署记录的后续文档提交单独验收其目标CI，不改变已运行程序SHA，
  不触发第二次服务切换。
