# -*- coding: utf-8 -*-
"""PRINT-TEMPLATE-F06 回归测试：打印模板在线编辑器 v2 引擎关键能力标记。

背景（需求 2026-09-09）：F05 编辑器行列删除不可靠、使用问题多，v2 改为
数据模型驱动引擎（先改数据再整体渲染）。本测试锚定 v2 引擎的关键实现
标记，防止被回退成旧版或删减核心能力：

  T1. 数据模型驱动标记：state 单元格模型（rs/cs/cov）与结构操作函数齐备
      （insertRow/deleteRow/insertCol/deleteCol/mergeSel/unmergeSel）
  T2. 撤销/重做快照命令栈标记（undoStack/redoStack/pushHistory/undo/redo）
  T3. 中文 IME 键盘捕获器标记（keyTrap + compositionend + flushKeyTrap）
  T4. 复制/剪切/粘贴标记（buildTSV/setInternalClip/pasteInternal/pasteTSV），
      且 copy/cut/paste 事件监听存在
  T5. 保存走全状态 DIFF 且 del_rows 恒为空数组（行列删除用清空模拟，
      避免后端 del_rows 合并区平移地雷）；读写必须走 WMS.api（A 规则）
  T6. 未保存提醒：anyDirty 脏标记 + beforeunload 拦截
  T7. 页面设置：@page 注入 + 纸张尺寸配置
  T8. 业务 JS 无 console.log/debugger/alert/eval 等调试残留（A3/A4/A5）
  T9. 冒烟测试钩子 window.__tplEditor 存在（自动化冒烟依赖）
"""
from __future__ import annotations

import re
from pathlib import Path

TPL = (
    Path(__file__).resolve().parent.parent
    / "app" / "templates" / "print_template_editor.html"
).read_text(encoding="utf-8")


def test_model_driven_structure_ops():
    """T1：数据模型驱动 + 行列结构操作函数齐备。"""
    for marker in ('function newCell()', 'rs: 1, cs: 1, cov: null',
                   'function insertRow(', 'function deleteRow(',
                   'function insertCol(', 'function deleteCol(',
                   'function mergeSel(', 'function unmergeSel(',
                   'function canMerge('):
        assert marker in TPL, f'缺少结构操作标记：{marker}'


def test_undo_redo_command_stack():
    """T2：撤销/重做快照命令栈。"""
    for marker in ('undoStack', 'redoStack', 'function pushHistory(',
                   'function undo(', 'function redo('):
        assert marker in TPL, f'缺少撤销栈标记：{marker}'
    assert "k === 'z' && !e.shiftKey" in TPL, 'Ctrl+Z 绑定缺失'
    assert "k === 'y' || (k === 'z' && e.shiftKey)" in TPL, 'Ctrl+Y 绑定缺失'


def test_ime_key_trap():
    """T3：中文 IME 键盘捕获器。"""
    for marker in ('id="keyTrap"', 'function flushKeyTrap(',
                   "compositionend", 'isComposing'):
        assert marker in TPL, f'缺少 IME 捕获器标记：{marker}'


def test_clipboard_support():
    """T4：复制/剪切/粘贴（内部带格式 + 外部 TSV）。"""
    for marker in ('function buildTSV(', 'function setInternalClip(',
                   'function pasteInternal(', 'function pasteTSV(',
                   "addEventListener('copy'", "addEventListener('cut'",
                   "addEventListener('paste'"):
        assert marker in TPL, f'缺少剪贴板标记：{marker}'


def test_save_full_state_diff_via_wms_api():
    """T5：保存为全状态 DIFF、del_rows 恒空、读写走 WMS.api。"""
    assert 'function buildSheetPayload(' in TPL, '缺少 DIFF 构造函数'
    assert 'del_rows: []' in TPL, 'del_rows 必须恒为空数组（删除用清空模拟）'
    assert 'WMS.api.get(BASE_URL)' in TPL, '读取必须走 WMS.api.get'
    assert 'WMS.api.post(BASE_URL' in TPL, '保存必须走 WMS.api.post'
    # 禁止原生非 GET fetch（A 规则）
    assert not re.search(r"fetch\s*\([^)]*method:\s*'(POST|PUT|DELETE|PATCH)'", TPL), \
        '禁止原生非 GET fetch，必须走 WMS.api'


def test_dirty_guard():
    """T6：未保存脏标记 + beforeunload 拦截。"""
    assert 'function anyDirty(' in TPL, '缺少脏标记判定'
    assert "beforeunload" in TPL, '缺少关闭拦截'


def test_page_setup():
    """T7：页面设置（@page 注入 + 纸张配置）。"""
    assert 'id="pageStyle"' in TPL, '缺少 @page 样式槽'
    assert "'@page{size:'" in TPL, '缺少 @page 注入逻辑'
    assert 'btnPageSetup' in TPL, '缺少页面设置入口'


def test_no_debug_residue():
    """T8：无调试残留（对齐 A3/A4/A5）。"""
    assert 'console.log' not in TPL, '存在 console.log 调试残留'
    assert 'debugger' not in TPL, '存在 debugger 调试残留'
    assert not re.search(r'\beval\s*\(|new Function\s*\(', TPL), '存在 eval/new Function'


def test_smoke_hook():
    """T9：自动化冒烟钩子。"""
    assert 'window.__tplEditor' in TPL, '缺少 window.__tplEditor 冒烟钩子'
