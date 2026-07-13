from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto('http://127.0.0.1:8080/login')
    page.wait_for_load_state('networkidle')
    
    # Login
    page.fill('input[name="username"]', 'admin')
    page.fill('input[name="password"]', 'admin')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    
    # Screenshot
    page.screenshot(path='/workspace/wms_full.png', full_page=True)
    
    # Check sidebar visibility
    sidebar = page.locator('#appSidebar')
    if sidebar.count() > 0:
        box = sidebar.bounding_box()
        print(f"Sidebar found: {box}")
        display = sidebar.evaluate('el => window.getComputedStyle(el).display')
        visibility = sidebar.evaluate('el => window.getComputedStyle(el).visibility')
        width = sidebar.evaluate('el => window.getComputedStyle(el).width')
        height = sidebar.evaluate('el => window.getComputedStyle(el).height')
        transform = sidebar.evaluate('el => window.getComputedStyle(el).transform')
        left = sidebar.evaluate('el => window.getComputedStyle(el).left')
        position = sidebar.evaluate('el => window.getComputedStyle(el).position')
        opacity = sidebar.evaluate('el => window.getComputedStyle(el).opacity')
        print(f"display={display} visibility={visibility} width={width} height={height}")
        print(f"transform={transform} left={left} position={position} opacity={opacity}")
    else:
        print("Sidebar NOT found in DOM")
    
    body_classes = page.evaluate('document.body.className')
    print(f"body class: '{body_classes}'")
    
    browser.close()
