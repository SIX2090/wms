import urllib.request, http.cookiejar, re
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
r = op.open('http://127.0.0.1:8080/login')
b = r.read().decode('utf-8', errors='ignore')
print('--- csrf lines ---')
for line in b.split('\n'):
    if 'csrf' in line.lower():
        print(line.strip()[:200])
print('--- form ---')
m = re.search(r'<form[^>]*>', b)
if m:
    print(m.group(0))
