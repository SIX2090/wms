# -*- coding: utf-8 -*-
"""腾讯云 一句话识别（SentenceRecognition）客户端。

仅依赖标准库 + requests，手工实现腾讯云 TC3-HMAC-SHA256 签名，
避免引入体积较大的 tencentcloud-sdk-python 依赖。

用途：手机端语音指令（AI-MOB-VOICE-F01 子修复）——App 录音上传到
WMS 后端，后端调用本模块把音频转成中文文本，再返回给 App 做关键词指令解析。

参考腾讯云 API v3 签名：https://cloud.tencent.com/document/api/213/47692
一句话识别接口：https://cloud.tencent.com/document/api/1093/35646
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
from typing import Any, Dict, Optional

import requests

ASR_HOST = "asr.tencentcloudapi.com"
ASR_ENDPOINT = "/"
ASR_VERSION = "2019-06-14"
ASR_ACTION = "SentenceRecognition"
ASR_REGION = "ap-guangzhou"


class TencentAsrError(Exception):
    """腾讯云一句话识别调用失败：含腾讯云返回的错误码/消息。"""


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, data: str) -> bytes:
    return hmac.new(key, data.encode("utf-8"), hashlib.sha256).digest()


def _sign(payload: bytes, secret_id: str, secret_key: str, region: str,
          host: str = ASR_HOST, action: str = ASR_ACTION,
          version: str = ASR_VERSION) -> Dict[str, str]:
    """构造腾讯云 API v3 请求头（TC3-HMAC-SHA256）。"""
    # 注意：不能用 datetime.utcnow().timestamp() —— naive 时间的 timestamp()
    # 会按本地时区解释，UTC+8 服务器上签名时间戳会落后 8 小时，
    # 导致腾讯云恒定返回 AuthFailure.SignatureExpire。time.time() 与时区无关。
    import time as _time
    ts = _time.time()
    timestamp = str(int(ts))
    date = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")

    content_type = "application/json; charset=utf-8"
    canonical_query = ""
    canonical_uri = ASR_ENDPOINT
    canonical_headers = "content-type:{0}\nhost:{1}\n".format(content_type, host)
    signed_headers = "content-type;host"

    canonical_request = "\n".join([
        "POST",
        canonical_uri,
        canonical_query,
        canonical_headers,
        signed_headers,
        _sha256_hex(payload),
    ])

    credential_scope = "{0}/{1}/tc3_request".format(date, "asr")
    string_to_sign = "\n".join([
        "TC3-HMAC-SHA256",
        timestamp,
        credential_scope,
        _sha256_hex(canonical_request.encode("utf-8")),
    ])

    secret_date = _hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, "asr")
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    authorization = (
        "TC3-HMAC-SHA256 "
        "Credential={0}/{1}, "
        "SignedHeaders={2}, "
        "Signature={3}"
    ).format(secret_id, credential_scope, signed_headers, signature)

    return {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Version": version,
        "X-TC-Timestamp": timestamp,
        "X-TC-Region": region,
    }


SUPPORTED_VOICE_FORMATS = {
    "wav", "mp3", "m4a", "aac", "pcm", "opus", "spx", "silk", "amr", "flac",
    "ogg", "wma", "caf",
}


def sentence_recognition(
    audio_bytes: bytes,
    secret_id: str,
    secret_key: str,
    region: str = ASR_REGION,
    voice_format: str = "wav",
    eng_service_type: str = "16k_zh",
    hotword_list: Optional[list] = None,
    timeout: float = 15.0,
) -> str:
    """调用腾讯云一句话识别，返回识别出的中文文本。

    :raises TencentAsrError: 参数非法 / 网络失败 / 腾讯云返回非成功结果。
    """
    fmt = (voice_format or "wav").lower().lstrip(".")
    if fmt not in SUPPORTED_VOICE_FORMATS:
        raise TencentAsrError("不支持的音频格式：{0}".format(voice_format))
    if not audio_bytes:
        raise TencentAsrError("音频数据为空")

    payload_body = {
        "EngSerViceType": eng_service_type,
        "SourceType": 1,
        "VoiceFormat": fmt,
        "Data": base64.b64encode(audio_bytes).decode("ascii"),
        # DataLen 为未 base64 的原始字节数，SourceType=1 时接口要求必传
        "DataLen": len(audio_bytes),
        # 注意：不要传 ChannelNum，一句话识别接口不认识该参数，
        # 传了会被腾讯云直接拒绝（UnknownParameter）
        "FilterDirty": 0,
        "FilterPunc": 0,
    }
    if hotword_list:
        # 腾讯云 HotwordList 为 String："热词|权重"，多词英文逗号分隔，最多 128 个。
        # 权重 100 开启同音增强替换（如 入库|100 会把 玉库 强制纠正为 入库）。
        payload_body["HotwordList"] = hotword_list
    payload = json.dumps(payload_body, ensure_ascii=False).encode("utf-8")

    headers = _sign(
        payload,
        secret_id=secret_id,
        secret_key=secret_key,
        region=region,
    )
    url = "https://{0}{1}".format(ASR_HOST, ASR_ENDPOINT)
    try:
        resp = requests.post(
            url, data=payload, headers=headers, timeout=timeout, verify=True
        )
    except requests.RequestException as e:  # 网络层失败
        raise TencentAsrError("腾讯云 ASR 网络请求失败：{0}".format(e)) from e

    try:
        data: Optional[Dict[str, Any]] = resp.json()
    except ValueError as e:
        raise TencentAsrError(
            "腾讯云 ASR 返回非 JSON：HTTP {0} {1}".format(resp.status_code, resp.text[:200])
        ) from e

    response = (data or {}).get("Response") or {}
    if response.get("Error"):
        detail = response["Error"]
        raise TencentAsrError(
            "腾讯云 ASR 错误 {code}: {message}".format(
                code=detail.get("Code", ""), message=detail.get("Message", "")
            )
        )
    text = (response.get("Result") or "").strip()
    if not text:
        raise TencentAsrError("腾讯云 ASR 未识别到内容")
    return text