import json, os, socket, base64, struct, time

WS_HOST = "127.0.0.1"
WS_PORT = 9222

def get_page_id():
    import urllib.request
    data = json.loads(urllib.request.urlopen(f"http://{WS_HOST}:{WS_PORT}/json/list").read())
    for t in data:
        if t.get("type") == "page":
            return t["id"]
    raise RuntimeError("No page target found")

WS_PATH = "/devtools/page/" + get_page_id()
print("Using page:", WS_PATH)

def ws_connect(host, port, path):
    s = socket.create_connection((host, port), timeout=10)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    s.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += s.recv(4096)
    if b" 101 " not in resp.split(b"\r\n", 1)[0]:
        raise RuntimeError("Handshake failed: " + resp[:200].decode())
    return s

def ws_send(s, payload):
    data = payload.encode()
    mask = os.urandom(4)
    header = bytearray([0x81])
    ln = len(data)
    if ln < 126:
        header.append(0x80 | ln)
    elif ln < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", ln)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", ln)
    header += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    s.sendall(bytes(header) + masked)

def ws_recv(s):
    def _read(n):
        buf = b""
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise EOFError
            buf += chunk
        return buf
    hdr = _read(2)
    opcode = hdr[0] & 0x0F
    ln = hdr[1] & 0x7F
    if ln == 126:
        ln = struct.unpack(">H", _read(2))[0]
    elif ln == 127:
        ln = struct.unpack(">Q", _read(8))[0]
    if hdr[1] & 0x80:
        _read(4)
    payload = _read(ln) if ln else b""
    return opcode, payload

def cdp(s, method, params=None, mid=None):
    _id = mid if mid is not None else int(time.time()*1000) % 100000000
    ws_send(s, json.dumps({"id": _id, "method": method, "params": params or {}}))
    while True:
        op, payload = ws_recv(s)
        if op == 1:
            d = json.loads(payload.decode())
            if d.get("id") == _id:
                return d

s = ws_connect(WS_HOST, WS_PORT, WS_PATH)
cdp(s, "Runtime.enable")
cdp(s, "DOM.enable")
cdp(s, "Page.enable")

def eval_js(expr):
    r = cdp(s, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r.get("result", {}).get("result", {}).get("value")

print("BEFORE URL:", eval_js("location.href"))

# 先登出
cdp(s, "Page.navigate", {"url": "http://127.0.0.1:8080/logout"})
time.sleep(3)

# 导航到登录页
cdp(s, "Page.navigate", {"url": "http://127.0.0.1:8080/login"})
time.sleep(4)
print("LOGIN URL:", eval_js("location.href"))
print("LOGIN TITLE:", eval_js("document.title"))

# 点击管理员 tab
eval_js("""
(function(){
  var tabs = document.querySelectorAll('[role=tab]');
  for(var i=0;i<tabs.length;i++){
    if(tabs[i].textContent.trim()==='管理员'){ tabs[i].click(); return 'clicked_admin'; }
  }
  return 'no_admin_tab';
})()
""")
time.sleep(1)

# 填写用户名密码并提交
result = eval_js("""
(function(){
  var u = document.querySelector('input[name=username]') || document.querySelector('input[type=text]');
  var p = document.querySelector('input[name=password]') || document.querySelector('input[type=password]');
  if(!u || !p) return 'NO_FIELDS';
  u.value='admin'; u.dispatchEvent(new Event('input',{bubbles:true}));
  p.value='admin'; p.dispatchEvent(new Event('input',{bubbles:true}));
  var f = u.form || p.form;
  if(f){ f.submit(); return 'SUBMITTED'; }
  return 'NO_FORM';
})()
""")
print("FILL:", result)
time.sleep(5)
print("AFTER_URL:", eval_js("location.href"))
print("AFTER_TITLE:", eval_js("document.title"))
print("AFTER_BODY:", (eval_js("document.body ? document.body.innerText.slice(0,500) : 'NO_BODY'") or ""))
s.close()
