"""Public OCR call evidence: keep diagnostics useful without provider details."""
import re


def public_ocr_error_message(error):
    """Keep actionable HTTP categories, never echo an upstream body or exception."""
    match = re.search(r'\bHTTP ([45]\d{2})\b', str(error or ''))
    if match:
        code = int(match.group(1))
        if code in (401, 403):
            return f'HTTP {code}：请核对图片识别接口和授权配置'
        if code == 429:
            return 'HTTP 429：图片识别服务繁忙，请稍后重试'
        return f'HTTP {code}：图片识别服务返回错误，请核对接口和图片格式'
    return '图片识别未完成，请核对接口配置或稍后重试'


def public_ocr_call_evidence(evidence):
    """Expose only bounded internal metrics and fixed error copy to the browser."""
    raw = evidence.to_dict()
    attempts = []
    for attempt in raw.get('attempts', []):
        attempts.append({key: attempt.get(key) for key in
                         ('attempt_no', 'error_type', 'duration_ms', 'has_reply')})
        attempts[-1]['error_message'] = public_ocr_error_message(attempt.get('error_message')) if attempt.get('error_type') else ''
    result = {key: raw.get(key) for key in
              ('total_attempts', 'success', 'final_error_type', 'total_duration_ms')}
    result['attempts'] = attempts
    result['final_error_message'] = public_ocr_error_message(raw.get('final_error_message')) if raw.get('final_error_type') else ''
    return result
