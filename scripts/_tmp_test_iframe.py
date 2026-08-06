import sys, threading, http.server, socketserver
from playwright.sync_api import sync_playwright

CHROME = "/root/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
APP = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:18082"
# parent origin must differ from APP origin (cross-site) to emulate IDE preview iframe

PARENT_PORT = 9999
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"""<!doctype html><html><body>
        <p>IDE parent (origin {self.request.getsockname()[0] if False else 'parent'})</p>
        <iframe id="app" src="{APP}/login" width=900 height=700></iframe>
        </body></html>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

srv = socketserver.TCPServer(("127.0.0.1", PARENT_PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True, args=["--no-sandbox"])
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto(f"http://127.0.0.1:{PARENT_PORT}/", wait_until="networkidle")
    print("PARENT URL:", page.url)
    # find the app iframe
    frame = page.frame_locator("#app")
    frame.locator("input[name=username]").fill("admin")
    frame.locator("input[name=password]").fill("admin")
    frame.locator("#loginBtn").click()
    page.wait_for_timeout(3000)
    print("COOKIES AFTER LOGIN:", ctx.cookies())
    # Now navigate the iframe itself to / and see if session persists
    # Access the iframe element's src/current url via frame
    app_frame = [f for f in page.frames if APP in (f.url or "")][0] if any(APP in (f.url or "") for f in page.frames) else None
    if app_frame:
        print("IFRAME URL AFTER LOGIN:", app_frame.url)
        # navigate iframe to APP root
        app_frame.goto(f"{APP}/", wait_until="networkidle")
        page.wait_for_timeout(2000)
        print("IFRAME URL AFTER NAV /:", app_frame.url)
        try:
            print("IFRAME TITLE:", app_frame.title())
        except Exception as e:
            print("TITLE ERR:", e)
    browser.close()