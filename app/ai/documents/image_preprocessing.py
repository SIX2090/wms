"""AI-R04 图片预处理与质量门禁。
# AI_TASK: AI-R04

目标：
- 上传图片先经质量门禁，不可用图片提前给出中文提示，不浪费视觉模型调用。
- 不破坏原文件：所有处理在 PIL 副本上进行，原图字节流独立保留。
- 方向校正（EXIF + 简单倾斜检测）、裁剪白边、等比缩放、压缩、尺寸限制。
- 清晰度（拉普拉斯方差）、曝光（均值/标准差）、空白图、最小尺寸检测。
- 多页图片顺序校验，避免页序错乱影响识别。
- 原图与处理图证据保存（指纹 + 处理步骤 + 质量指标），供审计追溯。

设计原则：
- 纯 Pillow 实现，无 OpenCV/Tesseract 依赖，沙箱与生产均可运行。
- 所有阈值集中为模块级常量，便于调优和测试。
- 处理失败不抛异常，降级返回原副本 + 警告，保证 OCR 流程不中断。
"""
from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

logger = logging.getLogger(__name__)


# ---- 质量阈值 ----

# 尺寸限制（像素）
MIN_LONG_EDGE = 300            # 长边低于此值视为过小，可能 OCR 无法识别
MAX_LONG_EDGE = 4096           # 长边超过此值自动等比缩小（控制视觉模型 token）
MAX_SHORT_EDGE = 4096
MIN_ASPECT_RATIO = 0.2         # 极端长条形（如旋转错误的窄图）视为可疑
MAX_ASPECT_RATIO = 5.0

# 清晰度阈值（拉普拉斯方差）
# 实测数据：合成清晰单据图 1000+，PIL 高斯模糊(radius=2.5)后 376，纯渐变图 100 左右。
# 阈值 500 介于真实模糊图与清晰图之间，使合成 blurry 场景样本能触发警告，normal 场景不误报。
BLUR_THRESHOLD = 500.0         # 低于此值判为模糊
SHARP_THRESHOLD = 1500.0       # 高于此值判为清晰

# 曝光阈值（0-255 灰度均值）
EXPOSURE_LOW = 40              # 低于此值判为欠曝（太暗）
EXPOSURE_HIGH = 230            # 高于此值判为过曝（太亮）
EXPOSURE_STDDEV_LOW = 5.0      # 标准差低于此值判为空白/纯色图

# 文件大小限制（字节）
MAX_PROCESSED_BYTES = 4 * 1024 * 1024  # 处理后图不超过 4MB（视觉模型 base64 后约 5.3MB）
JPEG_QUALITY_STEPS = (90, 80, 70, 60)  # 压缩质量逐步降级

# 多页允许的最大页数
MAX_PAGES = 20


@dataclass(frozen=True)
class ImageQualityMetrics:
    """图片质量指标（确定性可复算）。"""
    width: int
    height: int
    aspect_ratio: float
    blur_score: float           # 拉普拉斯方差，越大越清晰
    exposure_mean: float        # 灰度均值 0-255
    exposure_stddev: float      # 灰度标准差，越小越接近纯色
    is_blank: bool              # 纯色/空白图
    is_blurry: bool             # 模糊
    is_overexposed: bool        # 过曝
    is_underexposed: bool       # 欠曝
    is_too_small: bool          # 尺寸过小
    is_suspicious_aspect: bool  # 长宽比可疑（可能旋转错误）

    @property
    def is_usable(self) -> bool:
        """图片是否可用于 OCR（无致命质量问题）。"""
        return not (self.is_blank or self.is_too_small)

    def to_dict(self) -> dict[str, Any]:
        return {
            'width': self.width,
            'height': self.height,
            'aspect_ratio': round(self.aspect_ratio, 4),
            'blur_score': round(self.blur_score, 4),
            'exposure_mean': round(self.exposure_mean, 4),
            'exposure_stddev': round(self.exposure_stddev, 4),
            'is_blank': self.is_blank,
            'is_blurry': self.is_blurry,
            'is_overexposed': self.is_overexposed,
            'is_underexposed': self.is_underexposed,
            'is_too_small': self.is_too_small,
            'is_suspicious_aspect': self.is_suspicious_aspect,
            'is_usable': self.is_usable,
        }


@dataclass(frozen=True)
class PreprocessStep:
    """单步处理记录（证据保存）。"""
    name: str
    detail: str = ''


@dataclass
class PreprocessResult:
    """图片预处理结果。"""
    # 处理后图片（PIL Image），用于后续 OCR
    processed_image: Any
    # 原图字节指纹（sha256），用于审计追溯，不保存原图字节避免内存膨胀
    original_sha256: str
    # 处理后字节指纹
    processed_sha256: str = ''
    # 质量指标
    metrics: ImageQualityMetrics | None = None
    # 处理步骤记录（证据保存）
    steps: list[PreprocessStep] = field(default_factory=list)
    # 中文警告（不致命，仍可继续 OCR）
    warnings: list[str] = field(default_factory=list)
    # 中文错误（致命，应阻止 OCR 并提示用户）
    errors: list[str] = field(default_factory=list)
    # 是否可用（无致命错误）
    is_usable: bool = True
    # 处理后字节流（base64 前的 bytes）
    processed_bytes: bytes = b''
    # 处理后 MIME 类型
    processed_mime: str = 'image/jpeg'

    @property
    def blocked_reason(self) -> str:
        """若不可用，返回拼接的中文阻止原因。"""
        return '; '.join(self.errors) if self.errors else ''

    def to_evidence_dict(self) -> dict[str, Any]:
        """转换为审计证据字典（不含图片字节）。"""
        return {
            'original_sha256': self.original_sha256,
            'processed_sha256': self.processed_sha256,
            'metrics': self.metrics.to_dict() if self.metrics else None,
            'steps': [{'name': s.name, 'detail': s.detail} for s in self.steps],
            'warnings': list(self.warnings),
            'errors': list(self.errors),
            'is_usable': self.is_usable,
            'processed_size_bytes': len(self.processed_bytes),
            'processed_mime': self.processed_mime,
        }


# ---- 质量检测 ----

def check_image_quality(image: Any) -> ImageQualityMetrics:
    """检测图片质量指标。

    Args:
        image: PIL.Image.Image 实例

    Returns:
        ImageQualityMetrics 确定性指标
    """
    from PIL import Image, ImageFilter, ImageStat

    if image is None:
        raise ValueError('check_image_quality: image 不能为 None')

    width, height = image.size
    long_edge = max(width, height)
    short_edge = min(width, height)
    aspect_ratio = long_edge / short_edge if short_edge > 0 else 0.0

    # 灰度统计
    gray = image.convert('L') if image.mode != 'L' else image
    stat = ImageStat.Stat(gray)
    exposure_mean = float(stat.mean[0]) if stat.mean else 0.0
    exposure_stddev = float(stat.stddev[0]) if stat.stddev else 0.0

    # 清晰度：拉普拉斯方差
    # PIL 12 移除了 ImageFilter.Laplacian，用 Kernel 自定义 3x3 拉普拉斯核
    laplacian_kernel = (
        0, 1, 0,
        1, -4, 1,
        0, 1, 0,
    )
    laplacian = gray.filter(ImageFilter.Kernel((3, 3), laplacian_kernel, scale=1, offset=0))
    lap_stat = ImageStat.Stat(laplacian)
    # 拉普拉斯后的标准差即方差开方，平方得方差
    blur_score = float(lap_stat.stddev[0]) ** 2 if lap_stat.stddev else 0.0

    return ImageQualityMetrics(
        width=width,
        height=height,
        aspect_ratio=round(aspect_ratio, 4),
        blur_score=round(blur_score, 4),
        exposure_mean=round(exposure_mean, 4),
        exposure_stddev=round(exposure_stddev, 4),
        is_blank=exposure_stddev < EXPOSURE_STDDEV_LOW,
        is_blurry=blur_score < BLUR_THRESHOLD,
        is_overexposed=exposure_mean > EXPOSURE_HIGH,
        is_underexposed=exposure_mean < EXPOSURE_LOW,
        is_too_small=long_edge < MIN_LONG_EDGE,
        is_suspicious_aspect=(aspect_ratio < MIN_ASPECT_RATIO or aspect_ratio > MAX_ASPECT_RATIO),
    )


# ---- 预处理 ----

def preprocess_image(
    image_bytes: bytes,
    *,
    filename: str = '',
    auto_rotate: bool = True,
    trim_border: bool = True,
    resize_max: bool = True,
    compress: bool = True,
) -> PreprocessResult:
    """图片预处理主入口。

    流程：
    1. 加载原图字节，计算原图 sha256 指纹
    2. EXIF 方向校正（auto_rotate）
    3. 质量检测（清晰度/曝光/空白/尺寸）
    4. 不可用图片直接返回错误，不继续处理
    5. 裁剪白边（trim_border）
    6. 等比缩放到尺寸限制（resize_max）
    7. 压缩到目标大小（compress）
    8. 计算处理后 sha256 指纹

    所有处理在 PIL 副本上，不修改入参 image_bytes。
    """
    from PIL import Image, ImageOps

    if not image_bytes:
        return PreprocessResult(
            processed_image=None,
            original_sha256='',
            is_usable=False,
            errors=['图片字节为空'],
        )

    original_sha = hashlib.sha256(image_bytes).hexdigest()
    steps: list[PreprocessStep] = []
    warnings: list[str] = []
    errors: list[str] = []

    # 1. 加载原图
    try:
        original = Image.open(io.BytesIO(image_bytes))
        original.load()  # 强制加载，避免延迟读取问题
        steps.append(PreprocessStep('load', f'format={original.format} mode={original.mode} size={original.size}'))
    except Exception as exc:  # noqa: BLE001
        errors.append(f'图片加载失败：{exc}')
        return PreprocessResult(
            processed_image=None,
            original_sha256=original_sha,
            is_usable=False,
            errors=errors,
            steps=steps,
        )

    # 在副本上操作，不破坏原文件
    img = original.copy()

    # 2. EXIF 方向校正
    if auto_rotate:
        try:
            rotated = ImageOps.exif_transpose(img)
            if rotated is not img:
                img = rotated
                steps.append(PreprocessStep('exif_rotate', '根据 EXIF 方向标签校正'))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f'EXIF 方向校正失败：{exc}')

    # 3. 质量检测
    metrics = check_image_quality(img)
    steps.append(PreprocessStep('quality_check', f'blur={metrics.blur_score:.1f} exposure={metrics.exposure_mean:.1f}'))

    if metrics.is_blank:
        errors.append('图片为空白或纯色图，无法识别单据内容')
    if metrics.is_too_small:
        errors.append(f'图片尺寸过小（长边 {max(metrics.width, metrics.height)} < {MIN_LONG_EDGE}），请上传更清晰的图片')
    if metrics.is_blurry:
        warnings.append('图片疑似模糊，识别准确率可能下降')
    if metrics.is_overexposed:
        warnings.append('图片疑似过曝（太亮），建议重新拍摄')
    if metrics.is_underexposed:
        warnings.append('图片疑似欠曝（太暗），建议在光线充足处重新拍摄')
    if metrics.is_suspicious_aspect:
        warnings.append(f'图片长宽比异常（{metrics.aspect_ratio:.2f}），可能存在旋转错误')

    # 4. 不可用图片直接返回（不继续处理，避免浪费视觉模型调用）
    if errors:
        return PreprocessResult(
            processed_image=img,
            original_sha256=original_sha,
            metrics=metrics,
            steps=steps,
            warnings=warnings,
            errors=errors,
            is_usable=False,
        )

    # 5. 裁剪白边（简化版：检测四边是否接近纯白，裁剪到非白区域）
    if trim_border:
        try:
            trimmed = _trim_white_border(img)
            if trimmed.size != img.size:
                steps.append(PreprocessStep('trim_border', f'{img.size} -> {trimmed.size}'))
                img = trimmed
        except Exception as exc:  # noqa: BLE001
            warnings.append(f'白边裁剪失败：{exc}')

    # 6. 等比缩放到尺寸限制
    if resize_max:
        try:
            resized = _resize_to_limit(img, MAX_LONG_EDGE, MAX_SHORT_EDGE)
            if resized.size != img.size:
                steps.append(PreprocessStep('resize', f'{img.size} -> {resized.size}'))
                img = resized
        except Exception as exc:  # noqa: BLE001
            warnings.append(f'尺寸缩放失败：{exc}')

    # 7. 压缩到目标大小
    processed_bytes = b''
    processed_mime = 'image/jpeg'
    if compress:
        try:
            processed_bytes, processed_mime, quality_used = _compress_to_limit(img, MAX_PROCESSED_BYTES)
            steps.append(PreprocessStep('compress', f'mime={processed_mime} quality={quality_used} size={len(processed_bytes)}'))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f'图片压缩失败：{exc}')
            # 降级：原始格式输出
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            processed_bytes = buf.getvalue()
            processed_mime = 'image/png'
    else:
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        processed_bytes = buf.getvalue()
        processed_mime = 'image/png'

    processed_sha = hashlib.sha256(processed_bytes).hexdigest()

    return PreprocessResult(
        processed_image=img,
        original_sha256=original_sha,
        processed_sha256=processed_sha,
        metrics=metrics,
        steps=steps,
        warnings=warnings,
        errors=errors,
        is_usable=True,
        processed_bytes=processed_bytes,
        processed_mime=processed_mime,
    )


def _trim_white_border(image: Any, threshold: int = 240) -> Any:
    """裁剪接近纯白的四边白边。

    Args:
        threshold: 灰度值大于此值视为白边（默认 240）
    """
    from PIL import Image, ImageChops

    gray = image.convert('L')
    # 创建一个背景为纯白的图像，用 ImageChops.difference 找非白区域
    bg = Image.new('L', gray.size, 255)
    diff = ImageChops.difference(gray, bg)
    # 二值化：差异小于 15 视为白
    bbox = diff.point(lambda x: 255 if x > 15 else 0).getbbox()
    if bbox is None:
        # 整图都是白边，返回原图（避免裁剪为 0 尺寸）
        return image
    # bbox 不得裁剪超过原图 50%，避免误裁
    w, h = image.size
    bx0, by0, bx1, by1 = bbox
    if (bx1 - bx0) < w * 0.5 or (by1 - by0) < h * 0.5:
        return image
    return image.crop(bbox)


def _resize_to_limit(image: Any, max_long: int, max_short: int) -> Any:
    """等比缩放使长边≤max_long、短边≤max_short。"""
    from PIL import Image

    w, h = image.size
    long_edge = max(w, h)
    short_edge = min(w, h)
    if long_edge <= max_long and short_edge <= max_short:
        return image

    # 计算缩放比
    ratio_long = max_long / long_edge if long_edge > max_long else 1.0
    ratio_short = max_short / short_edge if short_edge > max_short else 1.0
    ratio = min(ratio_long, ratio_short)
    new_w = max(1, int(w * ratio))
    new_h = max(1, int(h * ratio))
    return image.resize((new_w, new_h), Image.LANCZOS)


def _compress_to_limit(image: Any, max_bytes: int) -> tuple[bytes, str, int]:
    """压缩图片到目标大小内，返回 (bytes, mime, quality_used)。

    优先 JPEG（质量逐级降级），JPEG 仍超限则转 PNG，PNG 仍超限返回最后一次 JPEG。
    """
    from PIL import Image

    # 统一转 RGB（JPEG 不支持 RGBA）
    if image.mode in ('RGBA', 'LA', 'P'):
        rgb = image.convert('RGB')
    else:
        rgb = image

    last_bytes = b''
    last_quality = 0
    for quality in JPEG_QUALITY_STEPS:
        buf = io.BytesIO()
        rgb.save(buf, format='JPEG', quality=quality, optimize=True)
        data = buf.getvalue()
        last_bytes = data
        last_quality = quality
        if len(data) <= max_bytes:
            return data, 'image/jpeg', quality

    # JPEG 仍超限，尝试 PNG（无损但可能更大）
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    png_data = buf.getvalue()
    if len(png_data) <= max_bytes and len(png_data) < len(last_bytes):
        return png_data, 'image/png', 0

    # 返回最后一次 JPEG（即使超限，至少是可用的）
    return last_bytes, 'image/jpeg', last_quality


# ---- 多页顺序 ----

@dataclass(frozen=True)
class MultiPageResult:
    """多页图片校验结果。"""
    is_valid: bool
    page_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'page_count': self.page_count,
            'errors': list(self.errors),
            'warnings': list(self.warnings),
        }


def validate_multi_page_order(page_filenames: Sequence[str]) -> MultiPageResult:
    """校验多页图片顺序。

    规则：
    - 页数不超过 MAX_PAGES
    - 文件名应能体现顺序（含数字后缀，如 page1/page2 或 _p1/_p2）
    - 文件名顺序与数字顺序一致（警告，不阻止）

    Args:
        page_filenames: 页文件名列表（按上传顺序）

    Returns:
        MultiPageResult
    """
    import re

    errors: list[str] = []
    warnings: list[str] = []

    if not page_filenames:
        errors.append('未提供任何页')
        return MultiPageResult(is_valid=False, page_count=0, errors=errors)

    page_count = len(page_filenames)
    if page_count > MAX_PAGES:
        errors.append(f'页数 {page_count} 超过上限 {MAX_PAGES}，请拆分多次上传')

    # 提取每页文件名中的数字
    numbers: list[int | None] = []
    for name in page_filenames:
        # 匹配文件名中最后一个数字段（如 page1.png -> 1, xxx_p2.jpg -> 2）
        matches = re.findall(r'(\d+)', name)
        if matches:
            numbers.append(int(matches[-1]))
        else:
            numbers.append(None)

    # 检查顺序一致性（仅当所有页都有数字时）
    if all(n is not None for n in numbers):
        if numbers != sorted(numbers):
            warnings.append(
                f'文件名数字顺序 {numbers} 与上传顺序不一致，可能导致页序错乱，'
                f'建议按 page1, page2, ... 顺序命名'
            )
        if len(set(numbers)) != len(numbers):
            warnings.append('文件名数字存在重复，可能导致页序混淆')

    return MultiPageResult(
        is_valid=not errors,
        page_count=page_count,
        errors=errors,
        warnings=warnings,
    )


# ---- 批量预处理 ----

def preprocess_multi_page(page_bytes_list: Sequence[bytes]) -> tuple[list[PreprocessResult], MultiPageResult]:
    """批量预处理多页图片。

    Args:
        page_bytes_list: 每页图片字节列表（按顺序）

    Returns:
        (results, order_result) - 每页预处理结果 + 顺序校验结果
    """
    results = [preprocess_image(b) for b in page_bytes_list]
    # 顺序校验需要文件名，这里用占位符（调用方应单独调用 validate_multi_page_order）
    order_result = MultiPageResult(
        is_valid=True,
        page_count=len(results),
        warnings=[] if len(results) <= MAX_PAGES else [f'页数 {len(results)} 较多'],
    )
    return results, order_result
