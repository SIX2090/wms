import urllib.request, http.cookiejar, re, urllib.parse

BASE = 'http://127.0.0.1:8080'
USER = 'admin'
PASS = 'AAAA1234'

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
b = op.open(BASE + '/login').read().decode('utf-8', errors='ignore')
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b).group(1)
data = urllib.parse.urlencode({'username': USER, 'password': PASS, 'csrf_token': csrf,
    'usage_consent': '1', 'login_mode': 'user'}).encode()
op.open(urllib.request.Request(BASE + '/login', data=data, headers={
    'User-Agent': 'dbg', 'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': BASE, 'Referer': BASE + '/login'}))

# After login, get the / page
for path in ['/', '/admin/console', '/in_order', '/in_order/add', '/category', '/stock_query']:
    try:
        r = op.open(BASE + path)
        b = r.read().decode('utf-8', errors='ignore')
        # title
        m = re.search(r'<title>([^<]+)</title>', b)
        title = m.group(1) if m else '(no title)'
        # check key strings
        has_ai = 'AI助手' in b or 'aiAssistant' in b
        has_lv1 = 'lv1' in b
        has_lv2 = 'lv2' in b
        has_badge = 'category-level-badge lv' in b
        has_path = '根分类到当前共' in b
        has_print = '/report/stock/print' in b
        has_no_data_badge = '无数据</span>' in b
        has_disable = 'disabled' in b
        has_ai_hide = 'aiAssistantHideBtn' in b
        has_ai_ls = 'wms_ai_hide_floating' in b
        print(f'== {path} == status=200 title={title}')
        print(f'   AI? {has_ai}  hideBtn? {has_ai_hide}  ls? {has_ai_ls}')
        print(f'   lv1? {has_lv1}  lv2? {has_lv2}  badge_class? {has_badge}  path? {has_path}')
        print(f'   print? {has_print}  no_data? {has_no_data_badge}  disabled? {has_disable}')
    except Exception as e:
        print(f'== {path} == ERR {e}')
