from playwright.sync_api import sync_playwright
import subprocess
import time

# Install dependencies if needed
try:
    subprocess.run(['playwright', 'install-deps', 'chromium'], check=True, capture_output=True)
except:
    pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    
    # Navigate to login
    page.goto('http://127.0.0.1:8080/login')
    page.wait_for_load_state('networkidle')
    
    # Login
    page.fill('input[name="username"]', 'admin')
    page.fill('input[name="password"]', 'admin')
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    
    # Take screenshot
    page.screenshot(path='/workspace/verify_sidebar.png', full_page=True)
    
    # Check sidebar
    sidebar = page.locator('#appSidebar')
    if sidebar.count() > 0:
        box = sidebar.bounding_box()
        print(f"✓ Sidebar found at: x={box['x']}, y={box['y']}, width={box['width']}, height={box['height']}")
        
        # Check if sidebar is visible (not transformed away)
        transform = sidebar.evaluate('el => window.getComputedStyle(el).transform')
        display = sidebar.evaluate('el => window.getComputedStyle(el).display')
        print(f"✓ Display: {display}, Transform: {transform}")
        
        if 'matrix' in transform and '0, 0' not in transform:
            print(" Sidebar might be transformed (moved)")
        else:
            print("✓ Sidebar is in normal position")
    else:
        print("✗ Sidebar NOT found")
    
    # Check body class
    body_class = page.evaluate('document.body.className')
    print(f"Body class: '{body_class}'")
    
    # Check if embedded-page is present
    has_embedded = page.evaluate('document.body.classList.contains("embedded-page")')
    print(f"Has embedded-page class: {has_embedded}")
    
    browser.close()
    print("\nScreenshot saved to /workspace/verify_sidebar.png")
