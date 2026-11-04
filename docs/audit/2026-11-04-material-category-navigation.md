# 物料分类切换清除旧搜索词（2026-11-04）

本批仅修复 BUG-2026-11-04-201。输入 `1.25-8` 搜索后，点击分类树任一入口自动清空搜索词、回到第一页，保留库存和启用状态筛选。选定分类后仍可在该分类内搜索，翻页和导出继续保留当前查询条件。

基线 `e69fdb484032a9d33e1fc844e16bc00ffe85fffb` 三工作流已核实；Android `3aeaaf1c2199ad03d4b2b2c4002f10277f5615ba` 为目标祖先且工程和工作流无变化。独立 main 副本 `C:/wms_audit/20261104_material_category_fix` 避开 `C:/wms` 现有未提交改动。

验证：旧模板专项6失败、1项对照通过；修后以下组合45通过（16项既有SQLAlchemy弃用警告）。新锁直接跟随服务端渲染的导航地址并检查返回表格和搜索框，覆盖父子分类、两个全部入口、旧页码清除、其他筛选保持及分类内搜索。

```powershell
python -m pytest -q tests/test_material_category_navigation.py tests/test_quick_select_enter_behavior.py tests/test_quick_select_lifecycle_runtime.py tests/test_bug_2026_09_05_004_material_export_category.py tests/test_material_status_toggle.py tests/test_filter_advanced.py tests/test_audit_material_search_normalization.py
```

统一门禁：`verify_wms_bugs.py`、常规规则、A11全量、UTF-8编码及diff检查通过；台账契约和A13测试15通过。`full_smoke_test.py`通过隔离Flask请求桥执行117/117通过，不连接网络；首次内存库因备份页仅支持文件库为116/117，改用全新隔离文件库后117/117。未修改产品或既有断言迁就环境。

验证日志和请求桥保留于 `C:/wms_audit/20261104_category_evidence`。实际推送及精确CI结果待补。生产尚未部署，生产需重启 WMS 服务生效；未操作生产业务记录、账号密码或服务。上线需另行授权。
