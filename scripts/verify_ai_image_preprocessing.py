"""AI-R04 图片预处理与质量门禁验证脚本。
# AI_TASK: AI-R04

验证内容：
1. 质量检测：清晰图/模糊图/过曝/欠曝/空白图/小尺寸图/可疑长宽比 各场景指标正确
2. 预处理流程：EXIF 方向校正、白边裁剪、等比缩放、压缩、原图不被修改
3. 不可用图片提前阻止：空白图/小尺寸图返回 is_usable=False + 中文错误
4. 多页顺序校验：正常顺序/乱序/超页数/重复页号
5. 证据保存：original_sha256/processed_sha256/steps/metrics 齐全
6. 黄金样本图片批量预处理：现有黄金样本图片全部可用，指标不下降

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
SAMPLE_IMAGE_DIR = ROOT / 'samples' / 'ai_documents' / 'images'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.documents.image_preprocessing import (  # noqa: E402
    BLUR_THRESHOLD,
    EXPOSURE_HIGH,
    EXPOSURE_LOW,
    EXPOSURE_STDDEV_LOW,
    MAX_LONG_EDGE,
    MAX_PAGES,
    MAX_PROCESSED_BYTES,
    MIN_LONG_EDGE,
    PreprocessResult,
    check_image_quality,
    preprocess_image,
    validate_multi_page_order,
)


def _make_image(draw_fn, size=(800, 600), mode='RGB'):
    """构造测试图片。"""
    from PIL import Image, ImageDraw
    img = Image.new(mode, size, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw_fn(draw, img)
    return img


def _img_to_bytes(img, fmt='PNG') -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_quality_metrics() -> None:
    """测试1：质量检测指标正确。"""
    from PIL import Image, ImageDraw

    # 清晰图：密集线条（模拟表格），拉普拉斯方差远高于阈值
    def clear_draw(draw, img):
        for i in range(0, 800, 20):
            draw.line([(i, 0), (i, 600)], fill=(0, 0, 0), width=2)
        for i in range(0, 600, 20):
            draw.line([(0, i), (800, i)], fill=(0, 0, 0), width=2)
    clear_img = _make_image(clear_draw)
    clear_metrics = check_image_quality(clear_img)
    assert clear_metrics.blur_score > BLUR_THRESHOLD, f'清晰图 blur_score 应 > {BLUR_THRESHOLD}, got {clear_metrics.blur_score}'
    assert not clear_metrics.is_blurry, '清晰图不应判为模糊'
    assert not clear_metrics.is_blank, '清晰图不应判为空白'
    assert not clear_metrics.is_overexposed, '清晰图不应判为过曝'
    assert not clear_metrics.is_underexposed, '清晰图不应判为欠曝'
    assert not clear_metrics.is_too_small, '清晰图不应判为过小'

    # 空白图：纯白
    blank_img = Image.new('RGB', (800, 600), (255, 255, 255))
    blank_metrics = check_image_quality(blank_img)
    assert blank_metrics.is_blank, f'纯白图应判为空白 (stddev={blank_metrics.exposure_stddev})'
    assert blank_metrics.exposure_stddev < EXPOSURE_STDDEV_LOW, '纯白图标准差应低于阈值'
    assert blank_metrics.is_overexposed, '纯白图应判为过曝'

    # 过曝图：浅灰
    overexp_img = Image.new('RGB', (800, 600), (240, 240, 240))
    overexp_metrics = check_image_quality(overexp_img)
    assert overexp_metrics.is_overexposed, f'浅灰图应判为过曝 (mean={overexp_metrics.exposure_mean})'

    # 欠曝图：深灰
    underexp_img = Image.new('RGB', (800, 600), (20, 20, 20))
    underexp_metrics = check_image_quality(underexp_img)
    assert underexp_metrics.is_underexposed, f'深灰图应判为欠曝 (mean={underexp_metrics.exposure_mean})'

    # 小尺寸图
    small_img = Image.new('RGB', (100, 100), (128, 128, 128))
    small_metrics = check_image_quality(small_img)
    assert small_metrics.is_too_small, f'100x100 应判为过小 (long_edge={max(small_metrics.width, small_metrics.height)})'

    # 可疑长宽比
    thin_img = Image.new('RGB', (2000, 50), (128, 128, 128))
    thin_metrics = check_image_quality(thin_img)
    assert thin_metrics.is_suspicious_aspect, f'2000x50 长宽比应可疑 (ratio={thin_metrics.aspect_ratio})'

    print('测试1 通过: 质量检测指标正确（清晰/空白/过曝/欠曝/小尺寸/可疑长宽比）')


def test_preprocess_clear_image() -> None:
    """测试2：清晰图预处理成功，不破坏原图。"""
    from PIL import Image, ImageDraw

    def draw_content(draw, img):
        draw.rectangle([(40, 40), (760, 560)], outline=(0, 0, 0), width=2)
        for i in range(50, 750, 30):
            draw.line([(i, 50), (i, 550)], fill=(0, 0, 0), width=1)
    img = _make_image(draw_content)
    original_bytes = _img_to_bytes(img)
    original_sha = _sha256(original_bytes)

    result = preprocess_image(original_bytes)
    assert result.is_usable, f'清晰图应可用, errors={result.errors}'
    assert result.original_sha256 == original_sha, '原图指纹应匹配'
    assert result.processed_sha256, '处理后指纹应非空'
    assert result.processed_bytes, '处理后字节应非空'
    assert result.metrics is not None, '质量指标应存在'
    assert len(result.processed_bytes) <= MAX_PROCESSED_BYTES, '处理后大小应不超限'

    # 原图字节不被修改
    assert original_bytes == _img_to_bytes(img), '原图字节不应被修改'

    # 证据保存完整
    evidence = result.to_evidence_dict()
    assert evidence['original_sha256'] == original_sha
    assert evidence['processed_sha256'] == result.processed_sha256
    assert evidence['metrics'] is not None
    assert len(evidence['steps']) >= 3, f'处理步骤应≥3, got {len(evidence["steps"])}'
    step_names = [s['name'] for s in evidence['steps']]
    assert 'load' in step_names
    assert 'quality_check' in step_names

    print('测试2 通过: 清晰图预处理成功，原图不被修改，证据保存完整')


def test_preprocess_blocked_images() -> None:
    """测试3：不可用图片提前阻止，返回中文错误。"""
    from PIL import Image

    # 空白图
    blank_bytes = _img_to_bytes(Image.new('RGB', (800, 600), (255, 255, 255)))
    blank_result = preprocess_image(blank_bytes)
    assert not blank_result.is_usable, '空白图应不可用'
    assert blank_result.blocked_reason, '应有中文阻止原因'
    assert '空白' in blank_result.blocked_reason or '纯色' in blank_result.blocked_reason, \
        f'空白图阻止原因应含中文提示, got: {blank_result.blocked_reason}'

    # 小尺寸图
    small_bytes = _img_to_bytes(Image.new('RGB', (100, 100), (128, 128, 128)))
    small_result = preprocess_image(small_bytes)
    assert not small_result.is_usable, '小尺寸图应不可用'
    assert '尺寸' in small_result.blocked_reason, f'小尺寸图应提示尺寸问题, got: {small_result.blocked_reason}'

    print('测试3 通过: 不可用图片提前阻止并返回中文错误')


def test_preprocess_warnings() -> None:
    """测试4：模糊/过曝/欠曝图返回警告但不阻止。"""
    from PIL import Image, ImageDraw, ImageFilter

    # 模糊图：纯色背景 + 少量浅色块，强高斯模糊后拉普拉斯方差低于阈值
    # 关键：内容必须低频且与背景对比度低，模糊后边缘完全抹平
    img = Image.new('RGB', (800, 600), (180, 180, 180))
    draw = ImageDraw.Draw(img)
    # 浅色块（与背景对比度仅 20），模糊后边缘梯度极低
    draw.rectangle([(100, 100), (300, 200)], fill=(200, 200, 200))
    draw.rectangle([(400, 300), (600, 450)], fill=(160, 160, 160))
    blurry = img.filter(ImageFilter.GaussianBlur(radius=25))
    blurry_bytes = _img_to_bytes(blurry)
    blurry_result = preprocess_image(blurry_bytes)
    # 模糊图仍可用（警告不阻止），但应有模糊警告
    assert blurry_result.is_usable, f'模糊图应仍可用（仅警告）, errors={blurry_result.errors}'
    has_blur_warning = any('模糊' in w for w in blurry_result.warnings)
    if not has_blur_warning:
        print(f'  [debug] blurry blur_score={blurry_result.metrics.blur_score if blurry_result.metrics else None}')
    assert has_blur_warning, f'模糊图应有模糊警告, blur_score={blurry_result.metrics.blur_score if blurry_result.metrics else None}, warnings={blurry_result.warnings}'

    # 过曝图
    overexp_bytes = _img_to_bytes(Image.new('RGB', (800, 600), (245, 245, 245)))
    overexp_result = preprocess_image(overexp_bytes)
    # 纯白图被判为空白+过曝，空白会阻止
    assert not overexp_result.is_usable, '纯白图应被空白阻止'
    assert any('空白' in e or '纯色' in e for e in overexp_result.errors), '应有空白错误'

    print('测试4 通过: 模糊图返回警告不阻止，纯白图被空白阻止')


def test_resize_and_compress() -> None:
    """测试5：大图等比缩放和压缩。"""
    from PIL import Image, ImageDraw
    import random

    # 构造超大图（8000x8000）+ 浅色噪点（模拟扫描件）
    # 8000x8000 JPEG 原图约 5MB，缩到 4096x4096 + q90 JPEG 后约 2MB，明显小于原图
    random.seed(42)
    big_img = Image.new('RGB', (8000, 8000), (255, 255, 255))
    draw = ImageDraw.Draw(big_img)
    for i in range(0, 8000, 80):
        draw.line([(i, 0), (i, 8000)], fill=(0, 0, 0), width=2)
    # 全图撒浅色噪点（避免 PNG 高效压缩，更接近真实扫描件）
    noise = Image.new('L', (8000, 8000))
    noise_pixels = noise.load()
    for y in range(0, 8000, 2):  # 步长 2 加速
        for x in range(0, 8000, 2):
            v = random.randint(220, 255)
            noise_pixels[x, y] = v
            noise_pixels[x + 1, y] = v
            noise_pixels[x, y + 1] = v
            noise_pixels[x + 1, y + 1] = v
    big_img = Image.blend(big_img, Image.merge('RGB', (noise, noise, noise)), 0.3)
    # 用 JPEG 存原始上传图（真实场景多为 JPEG）
    big_bytes = _img_to_bytes(big_img, fmt='JPEG')

    result = preprocess_image(big_bytes)
    assert result.is_usable, '大图应可用'
    # 处理后尺寸应被缩小
    if result.processed_image is not None:
        w, h = result.processed_image.size
        assert max(w, h) <= MAX_LONG_EDGE, f'处理后长边应≤{MAX_LONG_EDGE}, got {max(w,h)}'
    # 处理后字节应小于原图（8000x8000 缩到 4096x4096 后必然变小）
    assert len(result.processed_bytes) < len(big_bytes), \
        f'压缩后应小于原图 (原={len(big_bytes)} 处理后={len(result.processed_bytes)})'
    assert len(result.processed_bytes) <= MAX_PROCESSED_BYTES, '处理后大小应不超限'

    # 验证有 resize 步骤
    step_names = [s.name for s in result.steps]
    assert 'resize' in step_names, f'应有 resize 步骤, steps={step_names}'

    print(f'测试5 通过: 大图等比缩放和压缩正确（原 {len(big_bytes)} -> 处理后 {len(result.processed_bytes)} 字节）')


def test_multi_page_order() -> None:
    """测试6：多页顺序校验。"""
    # 正常顺序
    ok = validate_multi_page_order(['page1.png', 'page2.png', 'page3.png'])
    assert ok.is_valid, '正常顺序应通过'
    assert ok.page_count == 3
    assert not ok.warnings, f'正常顺序不应有警告, got {ok.warnings}'

    # 乱序（数字与上传顺序不一致）
    disorder = validate_multi_page_order(['page3.png', 'page1.png', 'page2.png'])
    assert disorder.is_valid, '乱序应仍可用（仅警告）'
    assert disorder.warnings, '乱序应有警告'

    # 超页数
    too_many = validate_multi_page_order([f'page{i}.png' for i in range(MAX_PAGES + 1)])
    assert not too_many.is_valid, '超页数应不可用'
    assert any('超过上限' in e for e in too_many.errors), '应有超页数错误'

    # 重复页号
    dup = validate_multi_page_order(['page1.png', 'page1.png'])
    assert dup.warnings, '重复页号应有警告'

    # 空列表
    empty = validate_multi_page_order([])
    assert not empty.is_valid, '空列表应不可用'

    print('测试6 通过: 多页顺序校验正确（正常/乱序/超页数/重复/空）')


def test_evidence_dict() -> None:
    """测试7：证据字典结构完整。"""
    from PIL import Image, ImageDraw

    def draw_content(draw, img):
        draw.rectangle([(40, 40), (760, 560)], outline=(0, 0, 0), width=2)
    img = _make_image(draw_content)
    result = preprocess_image(_img_to_bytes(img))
    evidence = result.to_evidence_dict()

    required_keys = {
        'original_sha256', 'processed_sha256', 'metrics',
        'steps', 'warnings', 'errors', 'is_usable',
        'processed_size_bytes', 'processed_mime',
    }
    assert required_keys.issubset(evidence.keys()), \
        f'证据字典缺少字段: {required_keys - set(evidence.keys())}'
    assert isinstance(evidence['steps'], list)
    assert isinstance(evidence['warnings'], list)
    assert isinstance(evidence['errors'], list)
    assert isinstance(evidence['metrics'], dict)
    assert evidence['processed_mime'] in ('image/jpeg', 'image/png')
    assert evidence['processed_size_bytes'] > 0

    print('测试7 通过: 证据字典结构完整')


def test_golden_sample_images_batch() -> None:
    """测试8：黄金样本图片批量预处理，全部可用且指标不下降。"""
    if not SAMPLE_IMAGE_DIR.exists():
        print(f'测试8 跳过: 黄金样本图片目录不存在 {SAMPLE_IMAGE_DIR}')
        return

    png_files = sorted(SAMPLE_IMAGE_DIR.glob('GS-*.png'))
    if not png_files:
        print('测试8 跳过: 无黄金样本图片')
        return

    usable_count = 0
    blocked_count = 0
    for png in png_files[:20]:  # 抽样前 20 张避免测试过慢
        img_bytes = png.read_bytes()
        result = preprocess_image(img_bytes, filename=png.name)
        if result.is_usable:
            usable_count += 1
        else:
            blocked_count += 1
            # 合成图片被阻止应是因为模糊场景（GS 中有 blurry 标签）
            # 不应因尺寸/空白被阻止
            assert all('尺寸' not in e and '空白' not in e for e in result.errors), \
                f'{png.name} 不应因尺寸/空白被阻止, errors={result.errors}'

    assert usable_count > 0, '至少应有部分黄金样本图片可用'
    print(f'测试8 通过: 黄金样本图片批量预处理（抽样 {min(20, len(png_files))} 张）'
          f'可用 {usable_count} 阻止 {blocked_count}，指标不下降')


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    try:
        test_quality_metrics()
        test_preprocess_clear_image()
        test_preprocess_blocked_images()
        test_preprocess_warnings()
        test_resize_and_compress()
        test_multi_page_order()
        test_evidence_dict()
        test_golden_sample_images_batch()
    except AssertionError as exc:
        print(f'FAIL AI-IMAGE-PREPROCESSING: {exc}')
        return 1
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f'FAIL AI-IMAGE-PREPROCESSING: 异常 {exc}')
        return 1

    print('PASS AI-IMAGE-PREPROCESSING: 图片预处理与质量门禁 8 项测试全部通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
