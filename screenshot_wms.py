import asyncio
from pyppeteer import launch

async def main():
    browser = await launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
    )
    page = await browser.newPage()
    await page.setViewport({'width': 1280, 'height': 720})
    await page.goto('http://127.0.0.1:8080/login', {'waitUntil': 'networkidle0'})
    await page.screenshot({'path': '/workspace/wms_login.png', 'fullPage': False})
    await browser.close()
    print("Screenshot saved to /workspace/wms_login.png")

asyncio.get_event_loop().run_until_complete(main())
