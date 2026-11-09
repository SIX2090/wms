# Windows 发布版本冲突修复（2026-11-09）

关联 BUG-2026-11-09-002。本批只将应用发行版本从2026.11.5递增到2026.11.6，并增加版本冲突回归、登记台账。原发布安全检查保持。

## 原因与范围

[Windows #105](https://github.com/SIX2090/wms/actions/runs/42551050755)与[#106](https://github.com/SIX2090/wms/actions/runs/42554321097)均在plan阶段报`Version tag conflicts with current committed build inputs.`，未执行下载、构建或上传。已有windows-v2026.11.5发布后，baf5ec6e改动app/templates/print_batch_labels.html但未递增app/version.py；2d2aecdf仅补文档，仍保留冲突。

全仓核对app/version.py、启动banner、Windows工作流自动/手动入口、tools/windows_release.py、portable导出/清单/运行检查、版本相关测试与脚本。Windows发行共用app/version.py；Android独立版本保持。网页/移动/AI/导入导出/报表/打印不单独生成Windows发行版本。本次确认的两个失败都由同一版本漏递增引起，未发现另一份需同步递增的Windows配置。历史发行不覆盖、不删除、不移动；版本一致性保护按原逻辑拒绝旧版本异输入复用。

## 开工门禁

远端main基线`2d2aecdf2fd2d67f74ded2fdc8319c900d60c939`：WMS CI [42554156686](https://github.com/SIX2090/wms/actions/runs/42554156686)、AI [42554156710](https://github.com/SIX2090/wms/actions/runs/42554156710)最新运行均completed/success。Android最新[42529810358](https://github.com/SIX2090/wms/actions/runs/42529810358)在`b5ab8d86cacddaeb4146ef9889f9482f079db352`成功；完整Git历史merge-base确认祖先关系，Android目录与构建工作流diff为空。匿名API查询403，使用已连接GitHub工具读取实际最新运行补证；不得把查询故障当绿色。

C:/wms存在其他任务未提交修改且本地落后，保留其所有文件和索引。本批在独立main检出`C:/Users/Administrator/AppData/Local/Temp/wms-release-20261109-main`开发，fetch后快进到真实远端基线，正常安装提交钩子，无新分支。

## 本地验证

修前5完整模块：Windows绑定、运行依赖门禁、portable安全、首次运行、发行清单，系统解释器105 passed/1 failed。唯一失败是测试解释器certifi2026.7.22/pypdf6.21.2不满足仓库锁定版本；在独立.venv安装certifi2026.10.18及pypdf6.21.4，不修改系统/生产解释器。原依赖门禁10项在该环境通过。

新增回归读取真实应用版本并模拟已发布2026.11.5的不同输入包，修前确实复现同一拒绝异常。修后7完整模块138 passed、0failed/skipped，包含原5发布模块及台账、物料标签相邻回归。命令：`.venv/Scripts/python.exe -m pytest tests/test_windows_release_binding.py tests/test_runtime_dependency_gate.py tests/test_audit_portable_safety.py tests/test_portable_first_run.py tests/test_release_manifest.py tests/test_f4_4_ledger_split.py tests/test_material_qr_label.py -q`。

R8物理撤回唯一产品改动app/version.py至原基线，Windows绑定完整模块1 failed/35 passed，唯一失败为新版本冲突锁；finally逐字节恢复版本文件，SHA256为`d90cacfaf2fcd3354038c0df0d65ebca4b70400902e6c939cc3efdf9ac9b15aa`，恢复后同模块36 passed。没有删除或放宽既有断言；台账契约仅新增本BUG状态映射，历史分布常量和全部断言保持。

`scripts/lint_wms_rules.py`全量0违规，`scripts/verify_wms_bugs.py`退出0，钩子安装/可执行检查通过。首次钩子检查仅因终端GBK无法输出勾号而失败，设置PYTHONUTF8/PYTHONIOENCODING后原检查通过。完整CI交精确代码提交运行，不在本地重复全站。

## 交付与生效边界

2026-11-09 15:00（北京时间）完成修复提交`9fc04d2b563217a46659d12ce023bcb6aaee3240`的实际交付验收：

- [WMS CI42575466739](https://github.com/SIX2090/wms/actions/runs/42575466739)：completed/success，完整分流；单元分片4379/4490/4537 passed，共13406 passed、206 skipped。静态、安全、四回归分片、隔离冒烟及真实Chrome均通过。
- [AI42575466850](https://github.com/SIX2090/wms/actions/runs/42575466850)：completed/success；Perf42575466799亦success。Android42529810358仍为最新成功运行，完整Git历史再次确认是目标祖先，Android源码及构建工作流无差异。
- [Windows42576050180](https://github.com/SIX2090/wms/actions/runs/42576050180)：completed/success，plan为build，真实下载、构建、临时安装验证、草稿上传核验与发布后核验全部成功，最终记录built_verified。
- [windows-v2026.11.6](https://github.com/SIX2090/wms/releases/tag/windows-v2026.11.6)：非draft的预览发行，实际来源9fc04d2b；ZIP、校验文件、release.json及runtime.json四资产均uploaded且有GitHub SHA256摘要。ZIP97133179字节，SHA256为`d1f19acc7e4d48795cf85451fac191c1832aff062dc88070c7d7cfeaa9e80224`；运行回执摘要`b8aa94866d7f411186ec730b6a97f45963657d22583b2ccb0869697588b2df99`。
- 输入指纹`fb9c9a558fb225899755dbc094e65677d5508aeb04b5a3b4ec18722f03c326fd`，制品身份`7982e46e68b2154260ab8134014f9705101c1278415e6706686c494c8deabcf9`，运行清单7357文件。证据来自实际Windows日志及发行API，不把本地合成回执当真实发行。

普通git push因本机配置的WorkBuddy凭据助手路径不存在而失败，未要求或提取明文凭据。改用已连接GitHub工具，以真实main基线为parent、base tree为基础，仅上传7个已验证文件；远端完整tree`0a767d4da29e8ab75667af8d66c7e9309a04b20f`与正常hooks生成的本地提交1ee63376完全一致，expected_sha匹配且force=false更新main。已保存本地提交bundle，fetch后核对parent/tree及准确变更集合，再仅对相同tree的独立检出对齐引用；HEAD与origin/main均为9fc04d2b，工作区干净，无reset/stash/新分支或伪造git push成功记录。

最后只补README/台账/本记录的实际验收事实，发布输入保持上述指纹，收尾提交按既有文档契约及精确目标门禁验收，Windows应核验同输入资产后记录reused_verified。本批不部署生产，不重启服务，不访问生产数据库或发送生产业务请求。历史#105/#106保留原失败证据，新工作流成功证明修复有效。
