import json, time
import websocket

WS = "ws://127.0.0.1:9222/devtools/page/969935910DEA17F5D7411F7447C5FD16"

def cdp(ws, method, params=None):
    mid = int(time.time()*1000) % 1000000
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        msg = ws.recv()
        d = json.loads(msg)
        if d.get("id") == mid:
            return d

ws = websocket.create_connection(WS, timeout=15, origin="https://chrome-devtools-frontend.appspot.com")
cdp(ws, "Runtime.enable")
cdp(ws, "DOM.enable")

def eval_js(expr):
    r = cdp(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r.get("result", {}).get("result", {}).get("value")

print("URL:", eval_js("location.href"))
print("TITLE:", eval_js("document.title"))
print("--- fields ---")
print(eval_js("""
(function(){
  var ins = Array.from(document.querySelectorAll('input'));
  return JSON.stringify(ins.map(function(i){return {name:i.name, type:i.type, id:i.id, placeholder:i.placeholder};}));
})()
"""))
print("--- fill & submit ---")
print(eval_js("""
(function(){
  var u = document.querySelector('input[name=username]') || document.querySelector('input[type=text]');
  var p = document.querySelector('input[name=password]') || document.querySelector('input[type=password]');
  if(!u || !p) return 'NO_FIELDS';
  u.value='admin'; u.dispatchEvent(new Event('input',{bubbles:true}));
  p.value='admin'; p.dispatchEvent(new Event('input',{bubbles:true}));
  var f = u.form || p.form;
  if(f){ f.submit(); return 'SUBMITTED_FORM'; }
  return 'NO_FORM';
})()
"""))
time.sleep(3)
print("--- after submit ---")
print("URL:", eval_js("location.href"))
print("TITLE:", eval_js("document.title"))
print("BODY:", eval_js("document.body ? document.body.innerText.slice(0,300) : 'NO_BODY'"))
ws.close()