from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # 导航到登录页面
    print("正在导航到登录页面...")
    page.goto('http://127.0.0.1:8080/login')
    page.wait_for_load_state('networkidle')
    
    # 填写用户名和密码
    print("正在填写登录表单...")
    page.fill('input[type="text"], input[name="username"], input[id="username"], input[placeholder*="用户名"]', 'admin')
    page.fill('input[type="password"], input[name="password"], input[id="password"], input[placeholder*="密码"]', 'admin')
    
    # 提交表单
    print("正在提交登录表单...")
    page.click('button[type="submit"], button:has-text("登录"), button:has-text("Login"), input[type="submit"]')
    
    # 等待导航完成
    print("等待页面加载...")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)  # 额外等待以确保页面完全加载
    
    # 截取全页面截图
    print("正在截取全页面截图...")
    page.screenshot(path='/workspace/wms_after_login.png', full_page=True)
    
    # 获取页面内容用于报告
    page_content = page.content()
    page_title = page.title()
    page_url = page.url
    
    print(f"\n页面标题: {page_title}")
    print(f"当前URL: {page_url}")
    print(f"截图已保存到: /workspace/wms_after_login.png")
    
    browser.close()
