import json, os, socket, base64, struct, hashlib, time

WS_HOST = "127.0.0.1"
WS_PORT = 9222
WS_PATH = "/devtools/page/969935910DEA17F5D7411F7447C5FD16"
TARGET = "http://127.0.0.1:16000/login"

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
# 先登出清理会话，再进登录页
cdp(s, "Page.navigate", {"url": "http://127.0.0.1:16000/logout"})
time.sleep(3)
cdp(s, "Page.navigate", {"url": TARGET})
time.sleep(4)
print("AFTER URL:", eval_js("location.href"))
print("TITLE:", eval_js("document.title"))
print("BODY:", (eval_js("document.body ? document.body.innerText.slice(0,200) : 'NO_BODY'") or ""))
s.close()