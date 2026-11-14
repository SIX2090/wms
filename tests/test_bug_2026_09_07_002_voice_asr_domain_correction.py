# -*- coding: utf-8 -*-
"""
BUG-2026-09-07-002 回归：语音指令识别强制收敛到仓库领域词。

用户实测（2026-09-07 截图实证）：
  - 说「领料」被识别成「饮料」，弹窗报「未识别到可执行指令」；
  - 说「入库」被识别成「欲哭」。
根因：
  ① 服务端热词表（/mobile/api/asr hotword_list）只有入库/出库权重 100，
     领料/盘点/查库存等核心指令词仅权重 5~11，同音替换约束力不足；
  ② 识别结果没有任何领域词纠正，腾讯云/系统识别/sherpa 的同音误识别
     原文直接进指令解析；
  ③ parseCommand 没有「领料」分支——即使识别正确也无法执行。

修复（三层防御）：
  ① 服务端 hotword_list 核心指令词全部提至权重 100（同音增强替换）；
  ② tencent_asr.correct_voice_asr_text 识别后按领域词表强制纠正；
  ③ Android 端 parseCommand 前同样纠正（覆盖系统识别/sherpa 路径），
     并新增 领料→出库 指令分支。

本文件覆盖 Python 侧：纠正函数行为 + 路由接线（热词权重 + 纠正应用）。
Android 侧与双端词表一致性见 tests/verify_bug_2026_09_07_002_voice_domain_correction.py。
"""
from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import User, db  # noqa: E402
from tencent_asr import VOICE_ASR_DOMAIN_CORRECTIONS, correct_voice_asr_text  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

_WAV = b"RIFF\x00\x00\x00\x00WAVEfmt \x00\x00\x00\x00\x00\x00\x00\x00data\x00\x00\x00\x00"


def test_correct_voice_asr_text():
    """A9 命名匹配 + 纠正函数行为全集。"""
    # 用户实测两条低级错误必须被纠正
    assert correct_voice_asr_text("饮料") == "领料"
    assert correct_voice_asr_text("欲哭") == "入库"
    assert correct_voice_asr_text("饮料。") == "领料。"
    # 词表抽查：同音/近音误识别 → 领域词
    assert correct_voice_asr_text("玉库") == "入库"
    assert correct_voice_asr_text("入裤") == "入库"
    assert correct_voice_asr_text("出裤") == "出库"
    assert correct_voice_asr_text("初库") == "出库"
    assert correct_voice_asr_text("裤存") == "库存"
    assert correct_voice_asr_text("查裤存") == "查库存"  # 组合指令
    assert correct_voice_asr_text("盘店") == "盘点"
    assert correct_voice_asr_text("潘点") == "盘点"
    assert correct_voice_asr_text("食物") == "识物"
    assert correct_voice_asr_text("起初") == "期初"
    assert correct_voice_asr_text("调播") == "调拨"
    assert correct_voice_asr_text("扫马") == "扫码"
    # 正确识别原样通过（不二次误伤）
    assert correct_voice_asr_text("入库") == "入库"
    assert correct_voice_asr_text("领料") == "领料"
    assert correct_voice_asr_text("查库存") == "查库存"
    assert correct_voice_asr_text("盘点") == "盘点"
    # 与仓库无关的普通文本不被篡改
    assert correct_voice_asr_text("今天天气不错") == "今天天气不错"
    # 破坏性操作不做强纠正（防误触发登出）
    assert "推出" not in VOICE_ASR_DOMAIN_CORRECTIONS
    # 空输入安全
    assert correct_voice_asr_text("") == ""
    assert correct_voice_asr_text(None) is None


def _reset_db():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        from werkzeug.security import generate_password_hash
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin",
            must_change_password=False,
        ))
        db.session.commit()


def _login(client):
    r = client.post("/login", data={
        "username": "admin", "password": "admin",
        "login_mode": "user", "usage_consent": "1",
    })
    assert r.status_code in (200, 302), r.get_data(as_text=True)


def test_asr_route_applies_domain_correction():
    """路由接线：腾讯云返回「饮料」→ 响应文本必须是纠正后的「领料」。"""
    os.environ["TENCENTCLOUD_SECRET_ID"] = "id"
    os.environ["TENCENTCLOUD_SECRET_KEY"] = "key"
    _reset_db()
    client = app_module.app.test_client()
    _login(client)
    with mock.patch("tencent_asr.sentence_recognition", return_value="饮料。"):
        r = client.post(
            "/mobile/api/asr",
            data={"audio": (BytesIO(_WAV), "cmd.wav")},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["status"] == "success"
    assert payload["text"] == "领料。"


def test_asr_route_hotword_weights_all_100():
    """路由接线：核心指令词热词权重必须全部 = 100（同音增强替换）。"""
    os.environ["TENCENTCLOUD_SECRET_ID"] = "id"
    os.environ["TENCENTCLOUD_SECRET_KEY"] = "key"
    _reset_db()
    client = app_module.app.test_client()
    _login(client)
    with mock.patch("tencent_asr.sentence_recognition", return_value="入库") as m:
        client.post(
            "/mobile/api/asr",
            data={"audio": (BytesIO(_WAV), "cmd.wav")},
            content_type="multipart/form-data",
        )
    m.assert_called_once()
    hotwords = m.call_args.kwargs["hotword_list"]
    pairs = dict(item.split("|") for item in hotwords.split(","))
    for word in ("入库", "出库", "领料", "盘点", "查库存", "库存",
                 "识物", "识别", "期初", "送货单", "退货", "调拨"):
        assert pairs.get(word) == "100", f"热词 {word} 权重必须 = 100，实际 {pairs.get(word)}"
