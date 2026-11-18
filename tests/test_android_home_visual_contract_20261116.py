from unittest.mock import patch

import pytest

from tests import verify_bug_2026_10_04_002_home_header_fab_position as position
from tests import verify_bug_2026_10_04_003_hero_selector_contrast as contrast


def test_home_guards_reject_invisible_title_and_selector_regressions():
    source = position.HOME.read_text(encoding='utf-8')
    position.test_002_title_and_warehouse_use_theme_surface()
    contrast.test_003_home_selector_uses_theme_foreground_on_surface()
    for old, new in (
        ('.background(Primary.readableOn(Color.White))', '.background(Color.White)'),
        ('contentColor = Color.White', 'contentColor = Color.Black'),
        # 2026-11-18 沉浸式品牌头：标题文案锁由「今日概览」改为问候语渲染点。
        ('Text(greeting', 'Text("其他标题"'),
    ):
        changed = source.replace(old, new)
        assert changed != source
        with patch.object(position, '_read', return_value=changed), pytest.raises(AssertionError):
            position.test_002_title_and_warehouse_use_theme_surface()
    for old, new in (
        ('contentColor = Color.White', 'contentColor = Color.Black'),
        ('onSelect = onSelectWarehouse', 'onSelect = {}'),
        ('allowAll = false', 'allowAll = true'),
    ):
        changed = source.replace(old, new)
        assert changed != source
        with patch.object(contrast, '_read', return_value=changed), pytest.raises(AssertionError):
            contrast.test_003_home_selector_uses_theme_foreground_on_surface()
