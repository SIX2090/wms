"""BUG-2026-07-28-011 简化验证：每次清空 cookie 后单次测试"""
import io
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar

BASE = "http://127.0.0.1:8080"


def fresh_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def http_get(opener, path):
    r = opener.open(f"{BASE}{path}", timeout=10)
    return r.status, r.read().decode("utf-8", errors="ignore")


def login_post(opener, username, password, consent='1', login_mode='user'):
    _, body = http_get(opener, "/login")
    csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    if not csrf:
        csrf = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', body)
    csrf = csrf.group(1) if csrf else ''
    data = urllib.parse.urlencode({
        "username": username,
        "password": password,
        "usage_consent": consent,
        "login_mode": login_mode,
        "csrf_token": csrf,
    }).encode()
    try:
        r = opener.open(f"{BASE}/login", data=data, timeout=10)
        return r.status, r.read().decode("utf-8", errors="ignore"), r.url
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore"), e.url


def parse_alert(body):
    alerts = re.findall(r'class="alert[^"]*"[^>]*>([^<]+)<', body)
    return [a.strip() for a in alerts]


def main():
    print('== BUG-011 简化验证 ==')

    # 1. 全新 cookie，输错 1 次
    print('\n[1] 全新 cookie 输错 1 次 admin/wrong')
    op = fresh_opener()
    status, body, url = login_post(op, 'admin', 'wrong-pwd-1')
    alerts = parse_alert(body)
    print(f'  status={status}, alerts={alerts}')
    # 找 ipFailedCount 与 remainingAttempts 文本值
    m_ip = re.search(r'<strong id="ipFailedCount">(\d+)</strong>', body)
    m_rm = re.search(r'<strong id="remainingAttempts">(\d+)</strong>', body)
    print(f'  ipFailedCount={m_ip.group(1) if m_ip else "N/A"}, remainingAttempts={m_rm.group(1) if m_rm else "N/A"}')
    # 检查 ipWarning 块是否带 hidden
    warn_hidden = 'id="ipWarning" class="ip-warning" hidden' in body
    print(f'  ipWarning hidden? {warn_hidden}')

    # 2. 同 cookie 继续输错 4 次（累计 5 次，触发锁定）
    print('\n[2] 同 cookie 继续输错 4 次触发锁定')
    last_status = None
    last_body = None
    for i in range(2, 7):
        # 每次都要重新拿 csrf（同一 cookie）
        op2 = op
        status, body, url = login_post(op2, 'admin', f'wrong-pwd-{i}')
        last_status = status
        last_body = body
        m_ip = re.search(r'<strong id="ipFailedCount">(\d+)</strong>', body)
        m_rm = re.search(r'<strong id="remainingAttempts">(\d+)</strong>', body)
        m_cd = re.search(r'id="lockCountdown" data-seconds="(\d+)"', body)
        cd_text = re.search(r'id="lockCountdown"[^>]*>(\d{2}:\d{2})<', body)
        cd_secs = int(m_cd.group(1)) if m_cd else 0
        cd_str = cd_text.group(1) if cd_text else 'N/A'
        print(f'  第 {i} 次: status={status} ip={m_ip.group(1) if m_ip else "-"} '
              f'rm={m_rm.group(1) if m_rm else "-"} '
              f'cd={cd_str}({cd_secs}s)')

    # 3. 锁定后再尝试一次
    print('\n[3] 锁定后再次提交')
    status, body, url = login_post(op, 'admin', 'still-wrong-after-lock')
    print(f'  status={status}')
    print(f'  alerts={parse_alert(body)}')
    m_cd = re.search(r'id="lockCountdown" data-seconds="(\d+)"', body)
    print(f'  lock_remaining_seconds={m_cd.group(1) if m_cd else "N/A"}')

    # 4. 验证：lockHint 不再 hidden
    assert 'id="lockHint" class="lock-hint"' in last_body
    assert 'id="lockHint" class="lock-hint" hidden' not in last_body
    print('\n[OK] lockHint 在锁定时正确显示')

    # 5. 验证：登录按钮 disabled
    btn_disabled = re.search(r'id="loginBtn"[^>]*disabled', last_body) is not None
    assert btn_disabled, '锁定时登录按钮未置灰'
    print('[OK] 登录按钮已置灰')

    print('\n[ALL PASS] BUG-2026-07-28-011 验证通过')


if __name__ == '__main__':
    main()
