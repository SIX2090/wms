# scripts/archive — 一次性脚本归档

> 2026-09-20 归档（P2-4 技术债清理）：这些文件是历次审计/E2E/验证/演示/止血修复的
> **一次性产物**，从仓库根目录迁入以减少噪音。**只归档、不删除**——保留供溯源，
> 不再属于日常开发路径；如需运行请自行核对相对路径（部分脚本按根目录定位写的）。
>
> 仍留在根目录的例外（**活依赖，不在归档范围**）：
> - `fix_p15_columns.py`——`tests/test_fix_db_columns.py` 活引用其 `MIGRATIONS`
>   （生产止血脚本与应用代码一致性断言）。
> - `fix_inventory_check_columns.bat`——`tests/test_fix_inventory_check_columns.py::
>   test_bat_script_wiring` 断言根目录必须存在该双击修复 bat。
>   2026-09-20 首次归档时误迁（CI #1146 红灯暴露），已迁回根目录。
>
> **教训（2026-09-20）**：归档前只按字符串 grep 引用不够——测试可能用
> `ROOT / "xxx.bat"` / `import xxx` 这类**拼接或动态**路径引用，文件名在测试里
> 未必以完整字面量出现。归档前应对每个文件跑全量 `pytest tests/`（或至少
> grep 文件名主干 + 后缀分开查），并在推送后盯 CI。
