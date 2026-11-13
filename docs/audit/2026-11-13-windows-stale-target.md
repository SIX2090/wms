# BUG-2026-11-13-005：并行提交使自动 Windows 发行目标过期时误报失败

本候选来自 `e68ff655ff22ad59b46873df5384b7623cfc9dcd` 的私有 Git 源码导出，只包含程序/规则/模板等筛选源码，不含生产数据库、备份、运行目录、凭据或环境文件；不修改共享 main、索引、历史、版本与台账。

## 已观察问题与根因

主任务报告 Windows Portable Release `43409733467` 对旧 `1faf2436` 在 Verify exact accepted main 步骤失败：main 已前进到 `e68ff655`，原 `$sha -ne $remote` 将正常并行推进当作失败。之后精确 `e68ff655` 的 `43410261471` 已由主任务验收 success。运行编号与状态是主任务实时取证提供，本子任务未调用 GitHub/gh 重新查询，也未把该运行结果当作候选验证。

AGENTS 已允许各任务独立推进和验收 CI。旧自动目标在开始前已失效，不应该继续打包，也不应该被报告为业务修复失败。tools/windows_release.py 在发布前和上传后已有 main 检查，但 main 前进时同样抛异常；plan 的资产下载窗口也需要同样处理。

## 最小变更

新增 `target_eligibility` 复用检查，仅当全部成立时返回 `stale_skipped`：实际调用环境为 workflow_run；目标和远端 main 都是完整 SHA；GitHub 查询成功；精确 fetch 当前 main 成功；Git 证明旧目标是新 main 的祖先。查询失败、缺失/非法 SHA、fetch 失败、非祖先或无法核实均继续失败；workflow_dispatch 和其他调用默认保留严格当前 main 限制。

- 工作流先核对 checkout 与精确触发 SHA，再调用 target 检查。过期自动目标输出 state/source_sha/current_main 和摘要，立即正常结束该步骤；后续三个 build-only 步骤全部不运行，最终摘要也不读取不存在的 plan。没有创建打包工作目录、下载、构建、上传或发布产物。
- 当前目标保持原 `check_ci_green.py --target-sha $sha --json`、版本、plan、离线依赖、实际临时安装、封存与发布验证。target 检查不能代替精确 CI 验收。
- plan 在创建工作目录前检查一次，在下载/复用校验后再次检查；检测自动目标已过期则弃用，本次计划明确标记 stale_skipped。
- publish 在任何 release create 之前和上传后的真实资产/归档校验之后再次检查。若构建期间推进，发布前直接弃用，没有 release create。若上传期间推进，保留本次未发布 draft 供审查，记录其 tag，绝不执行 `release edit --draft=false`，不擅删/移动已有标签或其他人的发行。
- publish 的 stale 结果写回本次计划，防止最终摘要把它当成 built_verified 或被以后复用为已验证构建。摘要明确旧目标、新 main 和未发布；上传途中产生的 draft 明确标为未发布候选。

默认手动调用行为不变。原 release inputs、源指纹、标签、归档清单/摘要、实际启动回执、完整四资产和上传后复核逻辑均保留；原测试文件不修改、不弱化断言。真正查询/祖先/资产/运行验证失败仍报错，不能转换成 stale skip。

## 验证与回退口径

`test_windows_release_stale_20261113.py` 直接用 -I -S -B 运行标准库 unittest：不导入 WMS，数据库与网络在测试进程被明确拒绝；target/plan/publish 的 GitHub/Git 操作用受控模型代替。PowerShell 用例提取真实工作流预检步骤，实际运行 PowerShell，但 git/gh/python 都是只记录/返回合成结果的函数替身，不执行真实 gh、网络、构建、下载或发布；检查 stale 立即结束、current 保留 CI→version→plan、查询失败不进入后续阶段。

原 test_windows_release_binding.py 全部原断言通过私有 fixture harness 执行，生产/网络/WMS 导入均被拒绝；仅允许本次新合成目录内的 Git init/config/add/commit/ls-tree 等元数据命令，使用独立空 Git 配置与模板目录，不执行宿主或 WMS hook。ZIP、manifest、receipt、版本与伪 GitHub 响应全为合成数据。该证据属于发布工具/控制流模型，不是实际 Windows 产品打包/发布。

私有源码副本将四文件按文档→测试→工作流→工具逆序回退，确认全部 2495 筛选源码 blob 回到固定基线；保护下执行旧 PowerShell 预检，复现自动祖先旧目标原异常，然后恢复精确候选重验。源代码回退不等于真实发行回退；目标 SHA 的完整 CI/实际 Windows 工作流须由主任务另验收。

## 交付边界

stale_skipped 只表示该自动目标已明确弃用，绝不计为产物构建完成、发布完成或业务 CI 修复成功。工作流保留真正当前 main 和精确 CI 打包门禁，不因并行推进放宽封存/回执/归档/发布断言。本轮没有构建、下载或发布任何真实 Windows 包，没有访问生产数据库/备份、现役业务服务、账号、单据，也没有部署或重启。生效确认：待人工确认。


统一集成验收：12文件在私有源码Git整批正常逆序回退，2440原始源码精确恢复；保留候选锁后旧stale处理按预期失败，恢复后8新模型及36原参数实例全部通过（不同计数口径分别报告）。本机实际PowerShell仅执行受控函数替身，Git/ZIP仅自有合成；未发GitHub或生产请求。回执 windows-stale-r8-proof.json；精确提交/CI/真实Windows发行后续补证，stale skip不得计构建完成。生效确认：待人工确认。
