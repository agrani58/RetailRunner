# order_bot.py
import asyncio
import time
import os
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

async def place_order_bot(frontend_url: str, user_info: dict, product_name: str):
    """
    Launches a visible Playwright browser and automates order placement.
    - frontend_url: e.g. "http://localhost:3000" or "http://44.219.130.221"
    - user_info: dict with keys: name, email, password, phone, address
    - product_name: exact product name to order
    """
    screenshots_dir = "order_screenshots"
    if not os.path.exists(screenshots_dir):
        os.makedirs(screenshots_dir)
    
    def log_step(step_num, description):
        print(f"\n{'='*60}")
        print(f"STEP {step_num}: {description}")
        print('='*60)
    
    async def take_screenshot(page, step_name):
        timestamp = time.strftime("%H%M%S")
        filename = f"{screenshots_dir}/{step_name}_{timestamp}.png"
        await page.screenshot(path=filename, full_page=True)
        print(f"📸 Screenshot: {filename}")
        return filename

    async def wait_and_fill(page, selector, value, description, timeout=5000):
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            await page.fill(selector, value)
            print(f"✅ Filled {description}: '{value}'")
            return True
        except Exception as e:
            print(f"❌ Failed to fill {description}: {e}")
            return False

    async def wait_and_click(page, selector, description, timeout=5000):
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            await page.click(selector)
            print(f"✅ Clicked: {description}")
            return True
        except Exception as e:
            print(f"❌ Failed to click {description}: {e}")
            return False

    print(f"\n🚀 Starting order bot for '{product_name}' on {frontend_url}")
    print(f"👤 User: {user_info['email']}")
    print("📱 Browser will open in a few seconds...\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=400,
            args=['--start-maximized']
        )
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(30000)

        try:
            # ---------------- STEP 1: ATTEMPT LOGIN ----------------
            log_step(1, "Attempting Login")
            await page.goto(f"{frontend_url}/login", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            await take_screenshot(page, "01_login_page")

            await page.fill('input[type="email"]', user_info["email"])
            await page.fill('input[type="password"]', user_info["password"])
            await page.click('button[type="submit"], button:has-text("Login")')
            await page.wait_for_timeout(3000)
            await take_screenshot(page, "02_after_login_click")

            # Check for login error
            error = await page.query_selector(
                '.error, .alert, .message, :text("Invalid"), :text("incorrect")'
            )
            if error:
                error_text = await error.text_content()
                print(f"⚠️ Login failed: {error_text}")

                # ----- STEP 2: REGISTER NEW USER -----
                log_step(2, "Registering New User")
                await page.goto(f"{frontend_url}/register", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                await take_screenshot(page, "03_register_page")

                # Fill registration form (assumes order: name, email, password, confirm password)
                inputs = await page.query_selector_all('input')
                values = [user_info["name"], user_info["email"], user_info["password"], user_info["password"]]
                for i in range(min(len(inputs), 4)):
                    await inputs[i].fill(values[i])
                    print(f"✅ Filled field {i+1}")

                await page.click('button[type="submit"], button:has-text("Register")')
                print("✅ Registration form submitted")
                await page.wait_for_timeout(3000)
                await take_screenshot(page, "04_after_registration")

                # If still on login/register page, attempt login again
                if "login" in page.url.lower() or "register" in page.url.lower():
                    print("🔑 Registration successful, logging in...")
                    await page.goto(f"{frontend_url}/login")
                    await page.wait_for_timeout(2000)
                    await page.fill('input[type="email"]', user_info["email"])
                    await page.fill('input[type="password"]', user_info["password"])
                    await page.click('button[type="submit"], button:has-text("Login")')
                    await page.wait_for_timeout(3000)
                    await take_screenshot(page, "05_after_login")
                else:
                    print("✅ Already logged in after registration")

            # Ensure we are on products page
            if "products" not in page.url:
                await page.goto(f"{frontend_url}/products")
                await page.wait_for_timeout(2000)
            await take_screenshot(page, "06_products_page")

            # ---------------- STEP 3: FIND PRODUCT ----------------
            log_step(3, "Finding Product")
            search_selectors = [
                'input[placeholder*="Search"]',
                'input[type="search"]',
                'input[name="search"]'
            ]
            for selector in search_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    await page.fill(selector, product_name)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(2000)
                    break
                except:
                    continue
            await take_screenshot(page, "07_after_search")

            # Click on product
            product_clicked = False
            try:
                await page.wait_for_selector(f'text={product_name}', timeout=3000)
                await page.click(f'text={product_name}')
                product_clicked = True
                print(f"✅ Clicked on '{product_name}'")
            except:
                # Try partial text
                elements = await page.query_selector_all('h2, h3, h4, .product-title, .product-name')
                for elem in elements:
                    text = await elem.text_content()
                    if text and product_name.lower() in text.lower():
                        await elem.click()
                        product_clicked = True
                        print(f"✅ Clicked on element containing '{product_name}'")
                        break
            if not product_clicked:
                print("⚠️ Could not find product, clicking first product")
                first_product = await page.query_selector('.product, .card, img, a')
                if first_product:
                    await first_product.click()
            await page.wait_for_timeout(2000)
            await take_screenshot(page, "08_product_detail")

            # ---------------- STEP 4: ADD TO CART ----------------
            log_step(4, "Adding to Cart")
            add_cart_selectors = [
                'button:has-text("Add to Cart")',
                'button:has-text("ADD TO CART")',
                'button[class*="add-to-cart"]',
                'button:has-text("Add")'
            ]
            added = False
            for selector in add_cart_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    await page.click(selector)
                    added = True
                    print("✅ Added to cart")
                    await page.wait_for_timeout(2000)
                    break
                except:
                    continue
            if not added:
                print("⚠️ Could not find add to cart button")
            await take_screenshot(page, "09_after_add")

            # ---------------- STEP 5: GO TO CART ----------------
            log_step(5, "Going to Cart")
            cart_clicked = False
            cart_selectors = [
                'a[href*="/cart"]',
                '.cart-icon',
                'button:has-text("Cart")',
                'a:has-text("Cart")'
            ]
            for selector in cart_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.click()
                        cart_clicked = True
                        print("✅ Clicked cart")
                        await page.wait_for_timeout(2000)
                        break
                except:
                    continue
            if not cart_clicked:
                print("⚠️ Going to /cart directly")
                await page.goto(f"{frontend_url}/cart")
            await take_screenshot(page, "10_cart_page")

            # ---------------- STEP 6: CHECKOUT ----------------
            log_step(6, "Proceeding to Checkout")
            checkout_clicked = False
            checkout_selectors = [
                'button:has-text("Proceed to Checkout")',
                'button:has-text("Checkout")',
                'a:has-text("Proceed to Checkout")',
                'a:has-text("Checkout")'
            ]
            for selector in checkout_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    await page.click(selector)
                    checkout_clicked = True
                    print("✅ Clicked checkout")
                    await page.wait_for_timeout(2000)
                    break
                except:
                    continue
            if not checkout_clicked:
                print("⚠️ Going to /checkout directly")
                await page.goto(f"{frontend_url}/checkout")
            await take_screenshot(page, "11_checkout_page")

            # ---------------- STEP 7: FILL SHIPPING INFO ----------------
            log_step(7, "Filling Shipping Info")
            all_inputs = await page.query_selector_all('input, textarea, select')
            for field in all_inputs:
                field_name = (await field.get_attribute('name') or '').lower()
                field_placeholder = (await field.get_attribute('placeholder') or '').lower()
                if any(k in field_name for k in ['name']) or any(k in field_placeholder for k in ['name']):
                    await field.fill(user_info["name"])
                    print("✅ Filled name")
                elif any(k in field_name for k in ['email']) or any(k in field_placeholder for k in ['email']):
                    await field.fill(user_info["email"])
                    print("✅ Filled email")
                elif any(k in field_name for k in ['phone', 'tel']) or any(k in field_placeholder for k in ['phone', 'tel']):
                    await field.fill(user_info["phone"])
                    print("✅ Filled phone")
                elif any(k in field_name for k in ['address']) or any(k in field_placeholder for k in ['address']):
                    await field.fill(user_info["address"])
                    print("✅ Filled address")
            await take_screenshot(page, "12_shipping_filled")

            # ---------------- STEP 8: CONTINUE ----------------
            log_step(8, "Continue to Payment")
            continue_btn = await page.query_selector('button[type="submit"], button:has-text("Continue"), button:has-text("Place Order")')
            if continue_btn:
                await continue_btn.click()
                print("✅ Clicked continue")
                await page.wait_for_timeout(2000)
            await take_screenshot(page, "13_payment_page")

            # ---------------- STEP 9: MANUAL PAYMENT ----------------
            log_step(9, "Manual Payment Required")
            print("\n" + "="*50)
            print("💰 MANUAL PAYMENT REQUIRED")
            print("="*50)
            print("\nPlease complete payment manually in the browser.")
            print("The browser will stay open until you press Enter.\n")
            input("Press Enter after completing payment to close browser...")

        except Exception as e:
            print(f"\n❌ Error in order bot: {e}")
            import traceback
            traceback.print_exc()
            try:
                await page.screenshot(path=f"{screenshots_dir}/error.png")
                print(f"\n📸 Error screenshot saved")
            except:
                pass
            input("\nPress Enter to close browser...")
        finally:
            try:
                await browser.close()
                print("\n✅ Browser closed")
            except:
                pass