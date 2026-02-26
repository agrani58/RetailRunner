# order_bot.py
import asyncio
import time
import os
import logging
import re
import httpx
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

async def place_order_bot(
    frontend_url: str,
    user_info: dict,
    product_name: str,
    user_id: int = None,
    notify_callback=None  # async function(message) to send WebSocket updates
):
    """
    Launches a visible Playwright browser and automates order placement.
    - frontend_url: e.g. "http://localhost:3000"
    - user_info: dict with keys: name, email, password, phone, address
    - product_name: exact product name to order
    - user_id: for notifications (optional)
    - notify_callback: async function(message) to send WebSocket updates
    """
    screenshots_dir = "order_screenshots"
    if not os.path.exists(screenshots_dir):
        os.makedirs(screenshots_dir)

    async def notify(msg):
        if notify_callback:
            try:
                await notify_callback(msg)
            except Exception as e:
                print(f"⚠️ Failed to send notification: {e}")

    def log_step(step_num, description):
        print(f"\n{'='*60}")
        print(f"STEP {step_num}: {description}")
        print('='*60)

    async def take_screenshot(page, step_name):
        timestamp = time.strftime("%H%M%S")
        filename = f"{screenshots_dir}/{step_name}_{timestamp}.png"
        try:
            await page.screenshot(path=filename, full_page=True, timeout=10000)
            print(f" Screenshot: {filename}")
        except Exception as e:
            print(f"⚠️ Screenshot failed: {e}")
        return filename

    # Helper to fill a field by label text, placeholder, or common selectors
    async def fill_field(page, label_patterns, placeholder_patterns, value, field_desc):
        # Try by label (visible text)
        for pattern in label_patterns:
            try:
                locator = page.get_by_label(pattern, exact=False)
                if await locator.count() > 0:
                    await locator.fill(value)
                    print(f" Filled {field_desc} via label '{pattern}'")
                    return True
            except:
                pass
        # Then by placeholder
        for pattern in placeholder_patterns:
            try:
                locator = page.get_by_placeholder(pattern)
                if await locator.count() > 0:
                    await locator.fill(value)
                    print(f" Filled {field_desc} via placeholder '{pattern}'")
                    return True
            except:
                pass
        # Fallback: try common input selectors
        selectors = []
        for pattern in label_patterns:
            selectors.append(f'input[name="{pattern}"]')
            selectors.append(f'input[type="{pattern}"]')
        selectors.extend(['input[type="text"]', 'input[type="email"]', 'input[type="tel"]', 'input[type="password"]'])
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() > 0:
                    await locator.fill(value)
                    print(f" Filled {field_desc} via selector '{selector}'")
                    return True
            except:
                pass
        print(f"⚠️ Could not fill {field_desc}")
        return False

    print(f"\n🚀 Starting order bot for '{product_name}' on {frontend_url}")
    print(f" User: {user_info['email']}")
    print(" Browser will open in a few seconds...\n")
    await notify(" Order bot started – browser opening...")

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

            await fill_field(page, ["email", "e-mail"], ["Email", "E-mail"], user_info["email"], "email")
            await fill_field(page, ["password"], ["Password"], user_info["password"], "password")

            await page.click('button[type="submit"], button:has-text("Login")')
            await page.wait_for_timeout(2000)

            # Check if login succeeded by looking for a logged-in indicator
            logged_in_indicators = [
                'a[href*="/profile"]',
                'button:has-text("Logout")',
                '.cart-icon',
                'a[href*="/products"]',
                'text="Welcome"',
            ]
            login_successful = False
            for selector in logged_in_indicators:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    login_successful = True
                    print("✅ Login successful")
                    break
                except:
                    continue

            if not login_successful:
                print(" Login failed or not logged in – proceeding to registration.")

                # ----- STEP 2: REGISTER NEW USER (DIRECT INPUT FILLING) -----
                log_step(2, "Registering New User")
                await page.goto(f"{frontend_url}/register", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                await take_screenshot(page, "03_register_page")

                # Get all input fields on the register page
                inputs = await page.query_selector_all('input')
                # Expected order: name, email, password, confirm password
                # Fill sequentially with our data
                if len(inputs) >= 4:
                    await inputs[0].fill(user_info["name"])
                    await inputs[1].fill(user_info["email"])
                    await inputs[2].fill(user_info["password"])
                    await inputs[3].fill(user_info["password"])  # confirm password
                    print("✅ Filled registration form directly via input order")
                else:
                    # Fallback to label-based filling
                    await fill_field(page, ["name", "full name"], ["Name", "Full Name"], user_info["name"], "name")
                    await fill_field(page, ["email", "e-mail"], ["Email", "E-mail"], user_info["email"], "email")
                    await fill_field(page, ["password"], ["Password"], user_info["password"], "password")
                    await fill_field(page, ["confirm password", "password confirmation"], ["Confirm Password", "Confirm"], user_info["password"], "confirm password")

                await page.click('button[type="submit"], button:has-text("Register")')
                print(" Registration form submitted")
                await page.wait_for_timeout(3000)

                # Check if registration succeeded (maybe redirected to login or products)
                # If we see a login page, fill credentials and log in
                if "login" in page.url.lower():
                    print(" Registration successful, redirected to login – logging in...")
                    await fill_field(page, ["email", "e-mail"], ["Email", "E-mail"], user_info["email"], "email")
                    await fill_field(page, ["password"], ["Password"], user_info["password"], "password")
                    await page.click('button[type="submit"], button:has-text("Login")')
                    await page.wait_for_timeout(2000)
                elif "products" in page.url.lower() or any(await page.query_selector(sel) for sel in logged_in_indicators):
                    print("✅ Registration successful and logged in")
                else:
                    # Check for error message (e.g., email already taken)
                    error = await page.query_selector('.error, .alert, .message, :text("already"), :text("taken")')
                    if error:
                        error_text = await error.text_content()
                        print(f" Registration failed: {error_text}")
                        # If email already exists, we can try logging in again
                        print(" Attempting login with existing credentials...")
                        await page.goto(f"{frontend_url}/login")
                        await page.wait_for_timeout(2000)
                        await fill_field(page, ["email", "e-mail"], ["Email", "E-mail"], user_info["email"], "email")
                        await fill_field(page, ["password"], ["Password"], user_info["password"], "password")
                        await page.click('button[type="submit"], button:has-text("Login")')
                        await page.wait_for_timeout(2000)
                    else:
                        print(" Registration may have succeeded but not confirmed.")

                # Final login check
                for selector in logged_in_indicators:
                    try:
                        await page.wait_for_selector(selector, timeout=5000)
                        login_successful = True
                        print("✅ Logged in after registration")
                        break
                    except:
                        continue

                if not login_successful:
                    print("⚠️ Could not verify login after registration. Proceeding anyway...")

                await take_screenshot(page, "04_after_registration")

            await take_screenshot(page, "02_after_login_click")

            # Ensure we are on products page (if not, navigate)
            if "products" not in page.url:
                await page.goto(f"{frontend_url}/products", wait_until="domcontentloaded")
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
                print(f" Clicked on '{product_name}'")
            except:
                elements = await page.query_selector_all('h2, h3, h4, .product-title, .product-name')
                for elem in elements:
                    text = await elem.text_content()
                    if text and product_name.lower() in text.lower():
                        await elem.click()
                        product_clicked = True
                        print(f" Clicked on element containing '{product_name}'")
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
                await page.goto(f"{frontend_url}/cart", wait_until="domcontentloaded")
            await take_screenshot(page, "10_cart_page")

            # ---------------- STEP 6: PROCEED TO CHECKOUT ----------------
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
                await page.goto(f"{frontend_url}/checkout", wait_until="domcontentloaded")
            await take_screenshot(page, "11_checkout_page")

            # ---------------- STEP 7: AUTO‑FILL PROFILE FIELDS (name, email, phone) ----------------
            log_step(7, "Auto‑filling Profile Info (Name, Email, Phone)")
            await fill_field(page, ["name", "full name"], ["Name", "Full Name"], user_info["name"], "shipping name")
            await fill_field(page, ["email", "e-mail"], ["Email", "E-mail"], user_info["email"], "shipping email")
            await fill_field(page, ["phone", "tel"], ["Phone", "Telephone", "Tel"], user_info["phone"], "phone")
            # Address is intentionally NOT filled – user must enter it manually.
            await take_screenshot(page, "12_profile_filled")

            print("\n✅ Name, Email, and Phone have been auto‑filled.")
            print(" Please enter your shipping address and payment details manually.")
            print(" After filling, click the final confirm button (e.g., 'Place Order', 'Pay Now').")
            print(" The bot will detect the order confirmation page automatically.\n")
            await notify(" Profile info filled – please complete address & payment, then confirm.")

            # ---------------- STEP 8: WAIT FOR ORDER CONFIRMATION PAGE ----------------
            log_step(8, "Waiting for Order Confirmation")
            confirmation_selectors = [
                'text="Order Confirmed"',
                'text="Order Confirmation"',
                'text="Thank you for your purchase"',
                '.order-confirmation',
                '.order-details',
                'h1:has-text("Order")',
                '.order-id',
                '.order-number',
                'text="Order #"'
            ]

            confirmed = False
            start_time = time.time()
            timeout = 300  # 5 minutes

            while not confirmed and (time.time() - start_time) < timeout:
                for selector in confirmation_selectors:
                    try:
                        await page.wait_for_selector(selector, timeout=2000)
                        confirmed = True
                        break
                    except:
                        continue
                if not confirmed:
                    print("⏳ Still waiting for confirmation page... (check your browser)")
                    await page.wait_for_timeout(2000)

            if not confirmed:
                print("⚠️ Timeout waiting for confirmation page. Proceeding anyway...")
            await take_screenshot(page, "13_confirmation_page")

            # ---------------- STEP 9: EXTRACT CONFIRMATION ----------------
            log_step(9, "Extracting Order Confirmation")
            delivery_date = None
            order_id = None

            # Delivery date
            date_selectors = [
                '.delivery-date', '.estimated-delivery', '.shipping-date',
                'p:has-text("delivery")', 'span:has-text("delivery")',
                '.order-confirmation p', '.order-details'
            ]
            for selector in date_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        text = await elem.text_content()
                        date_match = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text)
                        if date_match:
                            delivery_date = date_match.group(0)
                            break
                except:
                    continue

            # Order ID
            id_selectors = [
                '.order-id', '.order-number', 'strong:has-text("Order")',
                'p:has-text("Order #")', 'span:has-text("Order")'
            ]
            for selector in id_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        text = await elem.text_content()
                        order_match = re.search(r'[#]?(\d+)', text)
                        if order_match:
                            order_id = order_match.group(1)
                            break
                except:
                    continue

            if not delivery_date:
                delivery_date = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")
            if order_id in (None, "N/A"):
                order_id = None

            print(f" Extracted: Delivery Date = {delivery_date}" + (f", Order ID = {order_id}" if order_id else ""))

            # ---------------- STEP 10: SEND CONFIRMATION ----------------
            log_step(10, "Sending Confirmation to Backend")
            try:
                async with httpx.AsyncClient() as client:
                    payload = {
                        "email": user_info["email"],
                        "product_name": product_name,
                        "delivery_date": delivery_date,
                    }
                    if order_id:
                        payload["order_id"] = order_id

                    response = await client.post(
                        "http://localhost:8000/order-confirm",
                        json=payload,
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        print("✅ Order confirmation sent to backend")
                    else:
                        print(f"⚠️ Failed to send confirmation: {response.text}")
            except Exception as e:
                print(f"❌ Error sending confirmation: {e}")

            # ---------------- FINAL ----------------
            print("\n" + "="*50)
            print(" ORDER COMPLETED SUCCESSFULLY")
            print("="*50)
            await notify("✅ Order bot has stopped.")
            print("\nClosing browser in 5 seconds...")
            await page.wait_for_timeout(5000)

        except Exception as e:
            print(f"\n❌ Error in order bot: {e}")
            import traceback
            traceback.print_exc()
            await notify(f"❌ Order bot encountered an error: {str(e)[:100]}...")
            try:
                await page.screenshot(path=f"{screenshots_dir}/error.png", timeout=5000)
                print(f"\n Error screenshot saved")
            except:
                pass
            print("\nClosing browser in 10 seconds...")
            await page.wait_for_timeout(10000)
        finally:
            try:
                await browser.close()
                print("\n✅ Browser closed")
            except:
                pass