# full_order_bot_dynamic.py
import asyncio
import time
from playwright.async_api import async_playwright
import os
import sys

# ---------------- LOGGER ----------------
def log_step(step_num, description):
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {description}")
    print('='*60)

async def wait_and_click(page, selector, description, timeout=5000):
    try:
        await page.wait_for_selector(selector, state="visible", timeout=timeout)
        await page.click(selector)
        print(f"✅ Clicked: {description}")
        return True
    except Exception as e:
        print(f"❌ Failed to click {description}: {e}")
        return False

async def wait_and_fill(page, selector, value, description, timeout=5000):
    try:
        await page.wait_for_selector(selector, state="visible", timeout=timeout)
        await page.fill(selector, value)
        print(f"✅ Filled {description}: '{value}'")
        return True
    except Exception as e:
        print(f"❌ Failed to fill {description}: {e}")
        return False

async def take_screenshot(page, step_name):
    timestamp = time.strftime("%H%M%S")
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")
    filename = f"screenshots/{step_name}_{timestamp}.png"
    await page.screenshot(path=filename, full_page=True)
    print(f"📸 Screenshot: {filename}")
    return filename

# ---------------- MAIN BOT ----------------
async def main(user_info: dict, product_name: str):
    USER = user_info
    PRODUCT_NAME = product_name

    print("🚀 Starting Complete Order Bot")
    print(f"User: {USER['email']}")
    print(f"Product: {PRODUCT_NAME}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500, args=['--start-maximized'])
        page = await browser.new_page()
        page.set_default_timeout(10000)

        try:
            # ---------------- STEP 1: REGISTER ----------------
            log_step(1, "Registering New User")
            await page.goto("http://localhost:3000/register", wait_until="domcontentloaded", timeout=10000)
            inputs = await page.query_selector_all('input')
            values = [USER["name"], USER["email"], USER["password"], USER["password"]]
            for i in range(min(len(inputs), 4)):
                await inputs[i].fill(values[i])
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(3000)

            if "login" in page.url:
                await page.fill('input[type="email"]', USER["email"])
                await page.fill('input[type="password"]', USER["password"])
                await page.click('button[type="submit"]')
                await page.wait_for_timeout(2000)

            await take_screenshot(page, "01_after_registration")

            # ---------------- STEP 2: FIND PRODUCT ----------------
            log_step(2, "Finding Product")
            if "products" not in page.url:
                await page.goto("http://localhost:3000/products")
                await page.wait_for_timeout(2000)

            search_selectors = ['input[placeholder*="Search"]', 'input[type="search"]', 'input[name="search"]']
            for selector in search_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    await page.fill(selector, PRODUCT_NAME)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(2000)
                    break
                except:
                    continue

            try:
                await page.wait_for_selector(f'text={PRODUCT_NAME}', timeout=5000)
                product_element = await page.query_selector(f'text={PRODUCT_NAME}')
                if product_element:
                    await product_element.click()
            except:
                first_product = await page.query_selector('.product, .card, img, a')
                if first_product:
                    await first_product.click()

            await take_screenshot(page, "02_product_selected")

            # ---------------- STEP 3: ADD TO CART ----------------
            log_step(3, "Adding to Cart")
            add_cart_selectors = [
                'button:has-text("Add to Cart")',
                'button:has-text("ADD TO CART")',
                'text=Add to Cart',
                'button[class*="add-to-cart"]',
                'button:has-text("Add")'
            ]
            for selector in add_cart_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    await page.click(selector)
                    await page.wait_for_timeout(1000)
                    break
                except:
                    continue
            await take_screenshot(page, "03_added_to_cart")

            # ---------------- STEP 4: GO TO CART ----------------
            log_step(4, "Going to Cart")
            cart_icon_selectors = [
                'a[href*="/cart"]', 'a[href*="cart"]', '[href*="/cart"]', '.cart-icon',
                '.fa-shopping-cart', '[class*="cart"]', 'text=Cart', 'button:has-text("Cart")'
            ]
            cart_clicked = False
            for selector in cart_icon_selectors:
                try:
                    await page.wait_for_timeout(1000)
                    elements = await page.query_selector_all(selector)
                    if elements:
                        for elem in elements:
                            text = await elem.text_content() or ""
                            href = await elem.get_attribute("href") or ""
                            if "cart" in text.lower() or "cart" in href.lower():
                                await elem.click()
                                await page.wait_for_timeout(2000)
                                cart_clicked = True
                                break
                        if cart_clicked:
                            break
                except:
                    continue
            if not cart_clicked:
                await page.goto("http://localhost:3000/cart")
            await take_screenshot(page, "04_cart_page")

            # ---------------- STEP 5: CHECKOUT ----------------
            log_step(5, "Proceeding to Checkout")
            checkout_selectors = [
                'button:has-text("Proceed to Checkout")', 'button:has-text("Checkout")',
                'a:has-text("Proceed to Checkout")', 'a:has-text("Checkout")'
            ]
            checkout_clicked = False
            for selector in checkout_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    await page.click(selector)
                    checkout_clicked = True
                    break
                except:
                    continue
            if not checkout_clicked:
                await page.goto("http://localhost:3000/checkout")
            await take_screenshot(page, "05_checkout_page")

            # ---------------- STEP 6: FILL SHIPPING INFO ----------------
            log_step(6, "Filling Shipping Info")
            all_inputs = await page.query_selector_all('input, textarea, select')
            for field in all_inputs:
                field_type = await field.get_attribute('type') or 'text'
                field_name = await field.get_attribute('name') or ''
                field_placeholder = await field.get_attribute('placeholder') or ''
                if any(k in field_name.lower() for k in ['name']):
                    await field.fill(USER["name"])
                elif any(k in field_name.lower() for k in ['email']):
                    await field.fill(USER["email"])
                elif any(k in field_name.lower() for k in ['phone', 'tel']):
                    await field.fill(USER["phone"])
                elif any(k in field_name.lower() for k in ['address']):
                    await field.fill(USER["address"])
            await take_screenshot(page, "06_shipping_filled")

            # ---------------- STEP 7: MANUAL PAYMENT ----------------
            log_step(7, "Manual Payment Required")
            print("\n💰 Please complete payment manually in browser...")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            input("\nPress Enter to close browser...")
            await browser.close()
            print("\n✅ Browser closed")



    asyncio.run(main(user_info, product_name))
