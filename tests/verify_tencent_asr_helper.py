# -*- coding: utf-8 -*-
"""
腾讯云一句话识别助手（app/tencent_asr.py）静态 + 单元回归测试。

覆盖：
T1. TC3 签名请求头齐全（Authorization / X-TC-Action / X-TC-Version / X-TC-Timestamp / X-TC-Region）。
T2. 成功返回 Result 文本。
T3. 腾讯云返回 Error -> TencentAsrError。
T4. Result 为空 -> TencentAsrError。
T5. 不支持的音频格式 -> TencentAsrError。
T6. 空音频数据 -> TencentAsrError。
T7. 网络异常（requests 抛错）-> TencentAsrError。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

from tencent_asr import (  # noqa: E402
    SUPPORTED_VOICE_FORMATS,
    TencentAsrError,
    sentence_recognition,
)

SECRET_ID = "test_secret_id"
SECRET_KEY = "test_secret_key"


def _make_success_response():
    return mock.Mock(status_code=200, json=lambda: {
        "Response": {"Result": "入库", "RequestId": "req-1"}
    })


def test_t1_tc3_signature_headers_present():
    with mock.patch("tencent_asr.requests.post") as m:
        m.return_value = _make_success_response()
        sentence_recognition(b"RIFF_data", SECRET_ID, SECRET_KEY)
    headers = m.call_args.kwargs["headers"]
    assert headers["X-TC-Action"] == "SentenceRecognition"
    assert headers["X-TC-Version"] == "2019-06-14"
    assert headers["X-TC-Region"] == "ap-guangzhou"
    assert set(headers["X-TC-Timestamp"])
    assert headers["Authorization"].startswith(
        "TC3-HMAC-SHA256 Credential={0}/".format(SECRET_ID)
    )
    signed = m.call_args.kwargs["headers"]["Authorization"]
    assert "SignedHeaders=content-type;host" in signed
    assert "Signature=" in signed
    # 请求体必须包含 base64 音频数据
    payload = m.call_args.kwargs["data"]
    assert b"EngSerViceType" in payload
    assert b"SourceType" in payload


def test_t2_returns_result_text():
    with mock.patch("tencent_asr.requests.post") as m:
        m.return_value = _make_success_response()
        text = sentence_recognition(b"RIFF_data", SECRET_ID, SECRET_KEY)
    assert text == "入库"


def test_t3_raises_on_tencent_error():
    resp = mock.Mock(status_code=200, json=lambda: {
        "Response": {
            "Error": {"Code": "InvalidParameter", "Message": "参数错误"},
        }
    })
    with mock.patch("tencent_asr.requests.post") as m:
        m.return_value = resp
        try:
            sentence_recognition(b"RIFF_data", SECRET_ID, SECRET_KEY)
        except TencentAsrError as e:
            assert "InvalidParameter" in str(e)
            assert "参数错误" in str(e)
        else:
            raise AssertionError("应抛出 TencentAsrError")


def test_t4_raises_on_empty_result():
    resp = mock.Mock(status_code=200, json=lambda: {"Response": {"Result": "  "}})
    with mock.patch("tencent_asr.requests.post") as m:
        m.return_value = resp
        try:
            sentence_recognition(b"RIFF_data", SECRET_ID, SECRET_KEY)
        except TencentAsrError as e:
            assert "未识别到内容" in str(e)
        else:
            raise AssertionError("应抛出 TencentAsrError")


def test_t5_raises_on_unsupported_format():
    with mock.patch("tencent_asr.requests.post") as m:
        try:
            sentence_recognition(
                b"data", SECRET_ID, SECRET_KEY, voice_format="exe"
            )
        except TencentAsrError as e:
            assert "不支持的音频格式" in str(e)
            m.assert_not_called()
        else:
            raise AssertionError("应抛出 TencentAsrError")


def test_t6_raises_on_empty_audio():
    with mock.patch("tencent_asr.requests.post") as m:
        try:
            sentence_recognition(b"", SECRET_ID, SECRET_KEY)
        except TencentAsrError as e:
            assert "音频数据为空" in str(e)
            m.assert_not_called()
        else:
            raise AssertionError("应抛出 TencentAsrError")


def test_t7_raises_on_network_error():
    import requests
    with mock.patch(
        "tencent_asr.requests.post", side_effect=requests.ConnectionError("conn refused")
    ):
        try:
            sentence_recognition(b"RIFF_data", SECRET_ID, SECRET_KEY)
        except TencentAsrError as e:
            assert "网络请求失败" in str(e)
        else:
            raise AssertionError("应抛出 TencentAsrError")


def test_formats_whitelist_contains_wav():
    assert "wav" in SUPPORTED_VOICE_FORMATS
    assert "mp3" in SUPPORTED_VOICE_FORMATS


def test_sentence_recognition_success_path():
    """A9 唯一命名测试：验证 sentence_recognition 成功路径返回识别文本。"""
    with mock.patch("tencent_asr.requests.post") as m:
        m.return_value = _make_success_response()
        text = sentence_recognition(b"RIFF_data", SECRET_ID, SECRET_KEY)
    assert text == "入库"


def test_sentence_recognition():
    """A9 命名匹配：tests/ 目录需存在 def test_sentence_recognition( 以满足强制测试规则。

    与 test_sentence_recognition_success_path 逻辑等价，仅用于命名规范匹配。
    """
    with mock.patch("tencent_asr.requests.post") as m:
        m.return_value = _make_success_response()
        text = sentence_recognition(b"RIFF_data", SECRET_ID, SECRET_KEY)
    assert text == "入库"