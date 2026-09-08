# -*- coding: utf-8 -*-
"""BUG-2026-09-08-001 回归：标签模板字段（如物料名称）打印时静默丢失。

根因（三类同根消费点，规则 R6 一并修复）：
  ① Excel 风格设计器（material.html）删除行/列后不重排剩余单元格的
     data-row/data-col，序列化出的坐标可能越出声明的 rows×cols 网格；
  ② 批量打印页（print_batch_labels.html）渲染时仅按声明 rows×cols 迭代，
     越界坐标的单元格被静默丢弃——表现为某字段（物料名称）打印不出来；
  ③ `_normalize_label_template_layout` 发现 "行-列" 键控条目（旧设计器
     label_template_detail.html 格式）时整体丢弃 cells 列表（新设计器格式），
     两种格式并存的模板只剩键控条目里的字段。

修复：
  A. material.html 序列化（保存/草稿）前按 DOM 实际顺序重排坐标
     （reindexLabelCells，删除行/列链路经 saveTemplateToStorage 自动覆盖）；
  B. print_batch_labels.html 渲染网格 = max(声明 rows/cols, 单元格实际最大坐标+1)，
     越界单元格全部渲染；
  C. `_normalize_label_template_layout` 混合格式改为合并：列表全保留
     （同坐标列表优先），键控条目仅补充未占用坐标。

测试用例：
  T1. 混合格式合并：cells 列表单元格（含 name）全部保留，键控条目补充
      未占用坐标，同坐标不重复、列表优先
  T2. 纯键控布局维持原行为（回归保护：键控重建 cells 并排序）
  T3. print_batch_labels.html 静态契约：渲染网格覆盖单元格实际最大坐标
  T4. material.html 静态契约：序列化前重排坐标（保存/草稿双入口）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import app as m  # noqa: E402

PRINT_TEMPLATE = ROOT / "app" / "templates" / "print_batch_labels.html"
DESIGNER_TEMPLATE = ROOT / "app" / "templates" / "material.html"


def test_mixed_layout_merges_instead_of_discarding_list():
    """T1：键控条目与 cells 列表并存时合并，物料名称等列表字段不再被丢弃。"""
    layout = {
        'rows': 3,
        'cols': 1,
        'cells': [
            {'row': '0', 'col': '0', 'text': '[条码]', 'field': 'barcode', 'style': {}},
            {'row': '1', 'col': '0', 'text': '[物料名称]', 'field': 'name', 'style': {}},
        ],
        # 旧设计器遗留的键控条目：2-0 未占用（应补入），1-0 已占用（列表优先，不覆盖）
        '2-0': {'field': 'spec', 'label': '规格', 'style': {'fontSize': 10}},
        '1-0': {'field': 'unit', 'label': '单位', 'style': {}},
    }
    normalized = m._normalize_label_template_layout(layout)
    cells = normalized['cells']
    fields = [c.get('field') for c in cells]
    # 列表单元格全部保留（修复前 name/barcode 会被整体丢弃）
    assert 'barcode' in fields and 'name' in fields
    # 未占用坐标的键控条目补充进来
    assert 'spec' in fields
    # 同坐标列表优先：1-0 仍是 name，不会被键控的 unit 覆盖
    row1 = [c for c in cells
            if str(c.get('row')) == '1' and str(c.get('col')) == '0']
    assert len(row1) == 1 and row1[0]['field'] == 'name'
    # 补入的键控单元格带占位 text（设计器按 text 渲染占位符）
    spec_cell = [c for c in cells if c.get('field') == 'spec'][0]
    assert spec_cell.get('text') == '[规格]'


def test_keyed_only_layout_behavior_unchanged():
    """T2：纯键控布局仍按键控重建 cells 并排序（原行为回归保护）。"""
    layout = {
        '1-0': {'field': 'name', 'label': '物料名称', 'style': {}},
        '0-0': {'field': 'barcode', 'label': '条码', 'style': {}},
    }
    normalized = m._normalize_label_template_layout(layout)
    cells = normalized['cells']
    assert [c['field'] for c in cells] == ['barcode', 'name']
    assert cells[0]['row'] == 0 and cells[1]['row'] == 1
    # 无 field 的键控条目仍被忽略
    layout2 = {'0-0': {'label': '无字段'}, 'cells': []}
    assert m._normalize_label_template_layout(layout2)['cells'] == []


def test_print_page_grid_covers_actual_cell_coords():
    """T3：批量打印页渲染网格 = max(声明行列, 单元格实际最大坐标+1)。"""
    src = PRINT_TEMPLATE.read_text(encoding='utf-8')
    assert 'maxCellRow' in src and 'maxCellCol' in src
    assert 'Math.max(tmplData.rows || 1, maxCellRow + 1)' in src
    assert 'Math.max(tmplData.cols || 1, maxCellCol + 1)' in src
    # 渲染循环必须基于覆盖后的 rows/cols（防改回直接取声明值）
    assert 'var rows = tmplData.rows || 1;' not in src
    assert 'var cols = tmplData.cols || 1;' not in src


def test_designer_reindex_before_serialize():
    """T4：设计器序列化（保存/草稿）前按 DOM 实际顺序重排坐标。"""
    src = DESIGNER_TEMPLATE.read_text(encoding='utf-8')
    # 重排函数存在且按 DOM 行/列（含 colSpan）重写 data-row/data-col
    assert 'function reindexLabelCells()' in src
    assert 'cell.dataset.row = r;' in src
    assert 'cell.dataset.col = colPos;' in src
    # 保存到服务器前必须重排
    save_idx = src.index('function saveTemplate()')
    save_body = src[save_idx:save_idx + 1200]
    assert 'reindexLabelCells();' in save_body
    # 草稿序列化前必须重排（删除行/列链路经 saveTemplateToStorage 收尾覆盖）
    draft_idx = src.index('function saveTemplateToStorage()')
    draft_body = src[draft_idx:draft_idx + 600]
    assert 'reindexLabelCells();' in draft_body
