# 多任务并行与独立 CI 验收

2026-11-13，任务 `F2.8-PARALLEL-001`，按用户明确要求调整既有 F2.8/F3.16 策略：多个任务同时推进，各自的问题各自解决，不因一个任务等待 CI 阻塞其他任务。

## 范围与验收

- 同步 AGENTS、开发规范、BUG 基线的日常 CI 说明、AI 台账、README 和 CI 专题；取消单任务开发及跨任务全局等待。
- pre-push 不再查询全局 CI；保留 main 分支、有效提交 SHA、Windows 发行版本校验。
- WMS CI、AI、Android 和可选性能工作流取消分支级 concurrency，保留各目标运行；Windows 发行仍串行，防止产物发布冲突。
- CI 检查器按 main + 完整目标 SHA 查询最新运行。Android 无目标构建时仅查询该目标历史中最近修改 Android 输入的祖先，证明成功、对象、祖先和输入无变化后复用；不使用后续任务的新构建冒充旧目标证明。
- 共享 main 下明确文件归属、共享 Git 操作短暂协调，回退不得撤销其他任务。每个目标完整 CI 必须通过才可报告交付，生产部署另需授权且加载文件须匹配已验收快照。

开工基线：`cf3027a7d4423587ff4eb1477de244bafd79c48c`；WMS CI [43385925712](https://github.com/SIX2090/wms/actions/runs/43385925712)、AI [43385925571](https://github.com/SIX2090/wms/actions/runs/43385925571) success；Android [43384903895](https://github.com/SIX2090/wms/actions/runs/43384903895) 对应 `f965aa51a5eaf54614e6bf132e4b770a6beeff64` 成功，原检查器已证明成功祖先及输入未变。

## 本地验证

修前工具/相邻基线：154 passed / 3 skipped。测试显式列出 CI 检查器、钩子、编码和 CI 分流模块；它们不导入 WMS 应用、不使用数据库，使用 `--noconftest` 避免全站 conftest 导入生产应用初始化路径。Git 行为使用临时合成仓库，外部查询只涉及公开 GitHub Actions 元数据。

修后七个工具/相邻模块完整验证：192 passed / 1 skipped（无令牌的可选网络探测）；另一次钩子/并行专项 17/17 passed，集合重叠不累加。新增行为验证覆盖 A 已绿而 B 排队/运行/失败/取消、A 自身失败不能借 B 绿、旧目标 Android 证据不受新 main 影响、四工作流无跨提交取消，以及改发行输入未升版本仍被拒绝。

字节备份旧码对照：将六个旧实现文件复制到独立临时目录，使用新行为测试，14 failed / 3 passed；旧目标查询、工作流取消和推送阻塞均被实际检出。共享工作目录的候选文件未被回退或替换。规则 lint 0 违规、原生非 GET fetch 检查通过（存量模板 warn 保留）、源文件 UTF-8 检查及严格 AI 台账一致性通过。

本机直接执行全站 `verify_wms_bugs.py` 时，入口因没有真实 LPAC 合成身份而拒绝运行；未绕过保护，也未将此命令报告为本地通过。涉及应用导入的全站检查由精确目标 CI 的隔离环境执行并验收。

本地验证期间其他任务已将 main 推进到 `cedf7d783409513a3ed7ec5d9340ca01dc3a58a2` 并运行自己的 CI。本任务只检查该历史关系和文件归属，不等待它完成，也不取消它的验收。匿名 API 出现 403 限流后改用已连接 GitHub 工具公开读取运行元数据，不提取任何凭据。

## 提交与独立目标 CI

规则独立提交 `f0014862ff5f44fd98b3952cefaec458034cc19a`，实现与验证提交 `648cc6f1afb6162e36b204829f0cafc581533f71`。实际 `git push origin main` 输出 `cedf7d78..648cc6f1 main -> main`；推送后 HEAD、origin/main 和实时远端均核对为该完整目标。仅包含本任务 18 个规则、CI、工具测试及专项记录文件，无其他任务的 Android 改动。

2026-11-13 16:56（北京时间）通过已连接 GitHub 工具核对该目标全部必需运行均 completed/success：

- [WMS CI 43396235675](https://github.com/SIX2090/wms/actions/runs/43396235675)：完整分支，三个全站单测分片、四个脚本回归分片、真实 Chrome、隔离冒烟及静态/安全门禁通过；文档分支按设计跳过。
- [WMS AI Verification 43396235678](https://github.com/SIX2090/wms/actions/runs/43396235678)：完整验证通过。
- [Android APK Build 43396235792](https://github.com/SIX2090/wms/actions/runs/43396235792)：该目标实际构建、Android 单测和 lint 通过，未复用其他 SHA。
- 可选 [WMS Perf Baseline 43396235701](https://github.com/SIX2090/wms/actions/runs/43396235701) success。

本记录的后续纯文档收尾提交仍单独验收自身 CI，不以实现目标的成功冒充收尾提交已完成。

## 生效确认

规则与工具实现已完成推送及精确目标完整 CI 验收。确认人：本聊天代理；确认方式：实际 Git 推送/远端核对及上述 GitHub 同目标运行记录。未修改生产服务、数据库、账号或业务代码，不要求重启 WMS。工作区其他 Android 与测试改动不属于本任务，不纳入提交。
