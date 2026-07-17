"""AI-R03 合成黄金样本生成器。
# AI_TASK: AI-R03

用确定性种子生成 100 份合成中文单据样本，覆盖 5 来源类别 × 9 场景标签。
- 图片介质样本（photo/scanned/wechat_screenshot）用 PIL 生成对应样式图片并应用场景效果。
- 文本介质样本（wechat_text/excel）只生成 source_text。
- 每份样本的 expected 数据确定性生成，可重复。
- 原图和业务字段均经过脱敏（合成数据无真实 PII，desensitization_applied=True）。

用法：
    python scripts/generate_ai_golden_samples.py [--count 100] [--clean]

注意：合成图片的中文渲染依赖系统字体；沙箱无中文字体时图片会显示方框，
但表格结构和场景效果（模糊/倾斜/阴影）仍可验证，expected 数据在 JSON 元数据中完整保留。
真实 OCR 识别需配合真实样本，作为 AI-R03 遗留子项待用户提供后扩充。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
SAMPLE_DIR = ROOT / 'samples' / 'ai_documents'
IMAGE_DIR = SAMPLE_DIR / 'images'

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


# ---- 数据模板 ----

MATERIALS: list[dict[str, str]] = [
    {'code': '6204', 'name': '轴承', 'spec': '6204-2RS', 'unit': '套'},
    {'code': 'M8-NUT', 'name': '螺母', 'spec': 'M8', 'unit': '个'},
    {'code': 'M8-BOLT', 'name': '螺栓', 'spec': 'M8×30', 'unit': '个'},
    {'code': 'R10K', 'name': '电阻', 'spec': '10KΩ 0805', 'unit': '个'},
    {'code': 'C100N', 'name': '电容', 'spec': '100nF 0603', 'unit': '个'},
    {'code': 'LED-R', 'name': 'LED灯珠', 'spec': '红色 0805', 'unit': '个'},
    {'code': 'WIRE-2.5', 'name': '导线', 'spec': '2.5mm²', 'unit': '米'},
    {'code': 'SW-10A', 'name': '开关', 'spec': '10A 250V', 'unit': '个'},
    {'code': 'SOCKET-3', 'name': '插座', 'spec': '三孔 10A', 'unit': '个'},
    {'code': 'RELAY-12V', 'name': '继电器', 'spec': '12V 10A', 'unit': '个'},
]

SUPPLIERS = ['鑫达五金', '华强电子', '宏达机电', '顺发五金', '利达轴承']
CUSTOMERS = ['甲机械厂', '乙装备公司', '丙电子厂', '丁制造厂', '戊科技']
WAREHOUSES = ['主仓库', '电子仓', '五金仓', '原料仓', '成品仓']

# 单位混用场景：同一物料用不同单位
ALT_UNITS = {'套': '盒', '个': '只', '米': '卷', '盒': '箱'}

SCENARIOS = [
    'normal', 'blurry', 'tilted', 'shadow', 'handwritten',
    'multipage', 'merged_cell', 'duplicate', 'unit_mixed',
]

SOURCE_CATEGORIES = ['photo', 'scanned', 'wechat_screenshot', 'wechat_text', 'excel']

# 文档类型与草稿类型映射
DOC_DRAFT_MAP = {
    'in_order': 'in_order_draft',
    'out_order': 'out_order_draft',
    'sales_out_order': 'sales_out_draft',
    'transfer': 'transfer_draft',
    'purchase_request': 'purchase_request_draft',
}

# 确定性种子（可重复生成）
SEED = 20260717


# ---- 字体加载 ----

def load_font(size: int = 18):
    """加载中文字体，找不到则回退到默认字体。"""
    from PIL import ImageFont
    candidates = [
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


# ---- 样本数据生成 ----

def deterministic_material_id(code: str) -> int:
    """物料编码确定性映射到 material_id（1000-9999）。"""
    h = hashlib.sha1(code.encode('utf-8')).hexdigest()
    return 1000 + int(h[:8], 16) % 9000


def generate_expected(rng: random.Random, doc_type: str, scenario: str) -> dict[str, Any]:
    """生成期望识别结果。"""
    supplier = rng.choice(SUPPLIERS)
    customer = rng.choice(CUSTOMERS)
    warehouse = rng.choice(WAREHOUSES)
    order_no = f'{rng.choice(["SH", "CK", "DB", "PD", "XH"])}2026{rng.randint(10000, 99999)}'

    # 物料行数 2-5
    line_count = rng.randint(2, 5)
    chosen = rng.sample(MATERIALS, min(line_count, len(MATERIALS)))

    items: list[dict[str, Any]] = []
    for mat in chosen:
        item = {
            'code': mat['code'],
            'name': mat['name'],
            'spec': mat['spec'],
            'quantity': rng.choice([50, 100, 200, 500, 1000, 2000]),
            'unit': mat['unit'],
        }
        # 单位混用场景：部分行用替代单位
        if scenario == 'unit_mixed' and mat['unit'] in ALT_UNITS and rng.random() < 0.5:
            item['unit'] = ALT_UNITS[mat['unit']]
        items.append(item)

    # 重复行场景：复制一行
    if scenario == 'duplicate' and items:
        items.append(dict(items[0]))

    expected: dict[str, Any] = {
        'document_type': doc_type,
        'order_no': order_no,
        'warehouse': warehouse,
        'items': items,
    }
    if doc_type == 'in_order':
        expected['supplier'] = supplier
    elif doc_type == 'sales_out_order':
        expected['customer'] = customer
    elif doc_type == 'out_order':
        expected['customer'] = customer
    elif doc_type == 'transfer':
        expected['warehouse'] = warehouse
        expected['target_warehouse'] = rng.choice([w for w in WAREHOUSES if w != warehouse])

    return expected


def generate_material_matches(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """生成期望物料匹配结果。"""
    matches = []
    for item in items:
        matches.append({
            'code': item.get('code', ''),
            'match_method': 'exact_code' if item.get('code') else 'exact_name',
            'material_id': deterministic_material_id(item.get('code') or item.get('name', '')),
            'confidence': 0.95,
        })
    return matches


def build_source_text(sample_id: str, source_category: str, expected: dict[str, Any], scenario: str) -> str:
    """为文本介质样本生成 source_text。"""
    doc_type = expected.get('document_type', 'in_order')
    if source_category == 'wechat_text':
        # 微信文字送货通知格式：明天发XX 6204轴承 100套
        supplier = expected.get('supplier', '供应商')
        lines = [f'【{supplier}】明天发货清单：']
        for item in expected.get('items', []):
            lines.append(f'{item["code"]} {item["name"]} {int(item["quantity"])}{item["unit"]}')
        if scenario == 'duplicate':
            # 重复行场景：消息里重复发送
            first = expected.get('items', [{}])[0]
            lines.append(f'再确认一下 {first.get("code","")} {first.get("name","")} {int(first.get("quantity",0))}{first.get("unit","")}')
        return '\n'.join(lines)
    # excel：表格文本格式（TSV）
    header = '物料编码\t物料名称\t规格\t数量\t单位'
    rows = [header]
    for item in expected.get('items', []):
        rows.append(f'{item["code"]}\t{item["name"]}\t{item["spec"]}\t{item["quantity"]}\t{item["unit"]}')
    return '\n'.join(rows)


# ---- 图片生成 ----

def render_document_image(sample_id: str, source_category: str, expected: dict[str, Any],
                          scenario: str, image_path: Path) -> None:
    """用 PIL 生成单据图片并应用场景效果。"""
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

    width, height = 800, 600
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_lg = load_font(24)
    font_md = load_font(18)
    font_sm = load_font(14)

    # 标题
    title = {
        'photo': '送 货 单',
        'scanned': '送 货 单（扫描件）',
        'wechat_screenshot': '微信',
    }.get(source_category, '单 据')

    y = 20
    try:
        draw.text((width // 2 - 80, y), title, fill=(0, 0, 0), font=font_lg)
    except Exception:  # noqa: BLE001
        draw.text((width // 2 - 80, y), 'DELIVERY NOTE', fill=(0, 0, 0), font=font_lg)
    y += 40

    # 表头
    supplier = expected.get('supplier', expected.get('customer', ''))
    order_no = expected.get('order_no', '')
    try:
        draw.text((40, y), f'供应商：{supplier}', fill=(0, 0, 0), font=font_md)
        draw.text((450, y), f'单号：{order_no}', fill=(0, 0, 0), font=font_md)
    except Exception:  # noqa: BLE001
        draw.text((40, y), f'Supplier: {supplier}', fill=(0, 0, 0), font=font_md)
    y += 30

    # 表格
    table_top = y
    cols = [40, 180, 320, 460, 580, 700]
    headers = ['编码', '名称', '规格', '数量', '单位', '备注']
    try:
        for i, h in enumerate(headers):
            draw.text((cols[i] + 4, y + 4), h, fill=(0, 0, 0), font=font_sm)
    except Exception:  # noqa: BLE001
        for i, h in enumerate(['CODE', 'NAME', 'SPEC', 'QTY', 'UNIT', 'NOTE']):
            draw.text((cols[i] + 4, y + 4), h, fill=(0, 0, 0), font=font_sm)
    y += 28
    draw.line([(40, y), (760, y)], fill=(0, 0, 0), width=1)

    items = expected.get('items', [])
    # 多页场景：用更多行模拟
    if scenario == 'multipage':
        items = items * 3
    # 合并单元格场景：相邻同物料合并（图上简化为跨行竖线省略）
    merged_rows = set()
    if scenario == 'merged_cell' and len(items) >= 2:
        merged_rows = {1, 2}  # 第 2、3 行视觉合并

    for idx, item in enumerate(items):
        row_y = y + idx * 24
        if row_y > height - 40:
            break
        cells = [item.get('code', ''), item.get('name', ''), item.get('spec', ''),
                 str(item.get('quantity', '')), item.get('unit', ''), '']
        try:
            for i, c in enumerate(cells):
                draw.text((cols[i] + 4, row_y + 4), str(c), fill=(0, 0, 0), font=font_sm)
        except Exception:  # noqa: BLE001
            pass
        draw.line([(40, row_y + 24), (760, row_y + 24)], fill=(200, 200, 200), width=1)

    # 表格外框
    draw.rectangle([(40, table_top), (760, y + len(items) * 24 + 4)], outline=(0, 0, 0), width=1)

    # ---- 场景效果 ----
    if scenario == 'blurry':
        img = img.filter(ImageFilter.GaussianBlur(radius=2.5))
    elif scenario == 'tilted':
        img = img.rotate(-4, expand=False, fillcolor=(245, 245, 245))
    elif scenario == 'shadow':
        # 右侧阴影渐变
        gradient = Image.new('RGB', (width, height), (255, 255, 255))
        gd = ImageDraw.Draw(gradient)
        for x in range(width):
            shade = int(255 - (x / width) * 80)
            gd.line([(x, 0), (x, height)], fill=(shade, shade, shade))
        img = Image.blend(img, gradient, 0.35)
    elif scenario == 'handwritten':
        # 手写效果：降低对比度 + 轻微抖动
        img = ImageEnhance.Contrast(img).enhance(0.7)
        img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    elif scenario == 'low_light':
        img = ImageEnhance.Brightness(img).enhance(0.5)

    img.save(image_path, format='PNG')


def render_multipage_image(sample_id: str, source_category: str, expected: dict[str, Any],
                           scenario: str, image_path: Path) -> None:
    """多页场景生成 _page1/_page2 两张图，image_path 指向 page1。"""
    page1 = image_path
    page2 = image_path.with_name(image_path.stem + '_page2.png')
    render_document_image(sample_id, source_category, expected, 'normal', page1)
    # 第二页：换一组物料模拟续页
    page2_expected = dict(expected)
    page2_expected['items'] = expected.get('items', [])[::-1]
    render_document_image(sample_id + '_p2', source_category, page2_expected, 'normal', page2)


# ---- 主流程 ----

def generate_samples(count: int, clean: bool = False) -> int:
    """生成 count 份合成样本。"""
    rng = random.Random(SEED)

    # 清理旧合成样本（保留 LEGACY 旧样本）
    if clean:
        for path in SAMPLE_DIR.glob('GS-*.json'):
            path.unlink()
        for path in IMAGE_DIR.glob('GS-*.png'):
            path.unlink()
        for path in IMAGE_DIR.glob('GS-*_page2.png'):
            path.unlink()

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    # 文档类型分布：大部分是 in_order（送货单场景），少量其他类型
    doc_types = (['in_order'] * 70 + ['out_order'] * 12 + ['sales_out_order'] * 8
                 + ['transfer'] * 6 + ['purchase_request'] * 4)
    rng.shuffle(doc_types)

    # 每个来源类别均分 count 份
    per_source = count // len(SOURCE_CATEGORIES)
    remainder = count - per_source * len(SOURCE_CATEGORIES)

    generated = 0
    for src_idx, source_category in enumerate(SOURCE_CATEGORIES):
        n = per_source + (1 if src_idx < remainder else 0)
        for i in range(n):
            scenario = SCENARIOS[i % len(SCENARIOS)]
            doc_type = doc_types[(src_idx * per_source + i) % len(doc_types)]
            expected = generate_expected(rng, doc_type, scenario)
            sample_id = f'GS-{generated + 1:03d}'

            sample: dict[str, Any] = {
                'sample_id': sample_id,
                'sample_version': '1.0',
                'schema_version': '1.0',
                'source_category': source_category,
                'scenario_tags': [scenario],
                'usage_consent': 'synthetic',
                'desensitization_applied': True,
                'description': _build_description(source_category, scenario, doc_type, generated + 1),
                'expected': expected,
                'expected_draft_type': DOC_DRAFT_MAP.get(doc_type, 'none'),
                'expected_material_matches': generate_material_matches(expected.get('items', [])),
                'actual': None,
            }

            if source_category in ('photo', 'scanned', 'wechat_screenshot'):
                image_filename = f'{sample_id}.png'
                image_rel_path = f'images/{image_filename}'
                image_abs_path = IMAGE_DIR / image_filename
                sample['image_path'] = image_rel_path
                if scenario == 'multipage':
                    render_multipage_image(sample_id, source_category, expected, scenario, image_abs_path)
                else:
                    render_document_image(sample_id, source_category, expected, scenario, image_abs_path)
                sample['source_text'] = ''
            else:
                sample['image_path'] = ''
                sample['source_text'] = build_source_text(sample_id, source_category, expected, scenario)

            out_path = SAMPLE_DIR / f'{sample_id}.json'
            out_path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding='utf-8')
            generated += 1

    print(f'PASS generate-ai-golden-samples: 生成 {generated} 份合成样本到 {SAMPLE_DIR}')
    print(f'  图片介质样本图片目录：{IMAGE_DIR}')
    return 0


def _build_description(source_category: str, scenario: str, doc_type: str, idx: int) -> str:
    src_label = {
        'photo': '送货单照片',
        'scanned': '扫描件',
        'wechat_screenshot': '微信截图',
        'wechat_text': '微信文字通知',
        'excel': 'Excel表格',
    }.get(source_category, source_category)
    scenario_label = {
        'normal': '标准清晰',
        'blurry': '模糊',
        'tilted': '倾斜',
        'shadow': '阴影',
        'handwritten': '手写',
        'multipage': '多页',
        'merged_cell': '合并单元格',
        'duplicate': '重复行',
        'unit_mixed': '单位混用',
    }.get(scenario, scenario)
    return f'合成样本 {idx:03d}：{src_label} - {scenario_label} - {doc_type}'


def main() -> int:
    parser = argparse.ArgumentParser(description='生成 AI-R03 合成黄金样本。')
    parser.add_argument('--count', type=int, default=100, help='生成样本数（默认 100）')
    parser.add_argument('--clean', action='store_true', help='生成前清理旧合成样本（保留 LEGACY 旧样本）')
    args = parser.parse_args()
    return generate_samples(args.count, args.clean)


if __name__ == '__main__':
    raise SystemExit(main())
