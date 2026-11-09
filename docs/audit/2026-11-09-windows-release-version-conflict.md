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

精确提交的完整CI、Windows实际构建、四资产及真实运行回执待验。本批不部署生产，不重启服务，不访问生产数据库或发送生产业务请求。
