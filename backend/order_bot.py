import asyncio
import time
import os
import logging
import re
import httpx
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}

def _parse_delivery_date(text: str) -> str | None:
    text = text.strip()
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        return f"{y}-{mo:02d}-{d:02d}"
    m = re.search(
        r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?(?:[,\s]+(\d{4}))?\b",
        text
    )
    if m:
        month_str = m.group(1).lower()
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else datetime.now().year
        month_num = _MONTH_MAP.get(month_str)
        if month_num:
            try:
                dt = datetime(year, month_num, day)
                if dt.date() < datetime.now().date():
                    dt = dt.replace(year=dt.year + 1)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


async def place_order_bot(
    frontend_url: str,
    user_info: dict,
    product_name: str,
    user_id: int = None,
    notify_callback=None,
    payment_confirm_event: asyncio.Event = None,  # kept for compatibility
):
    """
    Order flow:
      1.  Login (or register)
      2.  Find product → Add to cart → Checkout
      3.  AUTO-FILL: name, email, phone
      4.  Click "Continue to Payment" / "Next"
      5.  Notify user to fill card details and click Pay
      6.  Wait for order confirmation page
      7.  Extract delivery date / order ID and POST to /order-confirm
    """
    async def notify(msg: str, msg_type: str = "bot_status"):
        print(f"[BOT NOTIFY] {msg_type}: {msg}")  # debug print
        if notify_callback:
            try:
                await notify_callback(msg, msg_type)
            except Exception as e:
                print(f"⚠️ Notify failed: {e}")

    def log_step(step_num, description):
        print(f"\n{'='*60}\nSTEP {step_num}: {description}\n{'='*60}")

    async def dump_inputs(page, label=""):
        try:
            inputs = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('input, textarea')).map(el => ({
                    tag: el.tagName, type: el.type || '', name: el.name || '',
                    id: el.id || '', placeholder: el.placeholder || '',
                    autocomplete: el.autocomplete || '', visible: el.offsetParent !== null
                }));
            }""")
            print(f"\n📋 Inputs [{label}]:")
            for inp in inputs:
                print(f"  {inp}")
        except Exception as e:
            print(f"⚠️ dump_inputs failed: {e}")

    async def smart_fill(page, value: str, field_desc: str,
                         names=(), ids=(), types=(), placeholders=(),
                         labels=(), autocompletes=(), is_textarea=False) -> bool:
        if not value:
            return False
        tag = "textarea" if is_textarea else "input"

        for n in names:
            try:
                loc = page.locator(f'{tag}[name="{n}"]')
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.scroll_into_view_if_needed()
                    await loc.first.click()
                    await loc.first.fill(value)
                    print(f" ✅ Filled '{field_desc}' via name='{n}'")
                    return True
            except Exception:
                pass

        for i in ids:
            try:
                loc = page.locator(f'#{i}')
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.scroll_into_view_if_needed()
                    await loc.first.click()
                    await loc.first.fill(value)
                    print(f" ✅ Filled '{field_desc}' via id='{i}'")
                    return True
            except Exception:
                pass

        for t in types:
            try:
                loc = page.locator(f'input[type="{t}"]')
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.scroll_into_view_if_needed()
                    await loc.first.click()
                    await loc.first.fill(value)
                    print(f" ✅ Filled '{field_desc}' via type='{t}'")
                    return True
            except Exception:
                pass

        for ph in placeholders:
            try:
                loc = page.locator(f'{tag}[placeholder*="{ph}" i]')
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.scroll_into_view_if_needed()
                    await loc.first.click()
                    await loc.first.fill(value)
                    print(f" ✅ Filled '{field_desc}' via placeholder~='{ph}'")
                    return True
            except Exception:
                pass

        for ac in autocompletes:
            try:
                loc = page.locator(f'input[autocomplete="{ac}"]')
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.scroll_into_view_if_needed()
                    await loc.first.click()
                    await loc.first.fill(value)
                    print(f" ✅ Filled '{field_desc}' via autocomplete='{ac}'")
                    return True
            except Exception:
                pass

        for lbl in labels:
            try:
                label_els = page.locator(f'label:has-text("{lbl}")')
                cnt = await label_els.count()
                for i in range(cnt):
                    for_attr = await label_els.nth(i).get_attribute("for")
                    if for_attr:
                        loc = page.locator(f'#{for_attr}')
                        if await loc.count() > 0 and await loc.first.is_visible():
                            await loc.first.scroll_into_view_if_needed()
                            await loc.first.click()
                            await loc.first.fill(value)
                            print(f" ✅ Filled '{field_desc}' via label[for='{for_attr}']")
                            return True
            except Exception:
                pass

        for lbl in labels:
            try:
                loc = page.get_by_label(lbl, exact=False)
                if await loc.count() > 0:
                    tag_name = await loc.first.evaluate("el => el.tagName.toLowerCase()")
                    if (is_textarea and tag_name == "textarea") or \
                       (not is_textarea and tag_name == "input"):
                        await loc.first.scroll_into_view_if_needed()
                        await loc.first.click()
                        await loc.first.fill(value)
                        print(f" ✅ Filled '{field_desc}' via get_by_label('{lbl}')")
                        return True
            except Exception:
                pass

        if is_textarea:
            try:
                textareas = page.locator("textarea")
                cnt = await textareas.count()
                for i in range(cnt):
                    ta = textareas.nth(i)
                    if await ta.is_visible():
                        current = await ta.input_value()
                        if not current.strip():
                            await ta.scroll_into_view_if_needed()
                            await ta.click()
                            await ta.fill(value)
                            print(f" ✅ Filled '{field_desc}' via first empty textarea")
                            return True
            except Exception:
                pass

        print(f" ⚠️ Could not fill '{field_desc}'")
        return False

    print(f"\n🚀 Starting order bot for '{product_name}' on {frontend_url}")
    await notify(f"🤖 Order bot starting for '{product_name}'…")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=250,
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        page.set_default_timeout(30000)

        try:
            # ── STEP 1: LOGIN ──────────────────────────────────────────────
            log_step(1, "Attempting Login")
            await notify("🔐 Logging into the store…")
            await page.goto(f"{frontend_url}/login", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            await dump_inputs(page, "login page")

            email_filled = await smart_fill(
                page, user_info["email"], "email",
                names=("email", "Email", "user_email", "username"),
                ids=("email", "user-email", "login-email"),
                types=("email",),
                placeholders=("email", "e-mail", "your email", "Enter email"),
                autocompletes=("email", "username"),
                labels=("Email", "E-mail", "Email address", "Email Address", "Username"),
            )
            pw_filled = await smart_fill(
                page, user_info["password"], "password",
                names=("password", "Password", "pass"),
                ids=("password", "user-password", "login-password"),
                types=("password",),
                placeholders=("password", "Password", "Enter password"),
                autocompletes=("current-password",),
                labels=("Password", "Pass"),
            )

            if not email_filled or not pw_filled:
                print("⚠️ Labeled fill failed — using positional fallback")
                inputs = page.locator('input:visible')
                cnt = await inputs.count()
                if cnt >= 2:
                    await inputs.nth(0).click(); await inputs.nth(0).fill(user_info["email"])
                    await inputs.nth(1).click(); await inputs.nth(1).fill(user_info["password"])

            for sel in ['button[type="submit"]', 'button:has-text("Login")',
                        'button:has-text("Sign in")', 'button:has-text("Log in")',
                        'input[type="submit"]']:
                try:
                    btn = page.locator(sel)
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.click(); break
                except Exception:
                    pass

            await page.wait_for_timeout(2500)

            login_success_selectors = [
                'a[href*="/profile"]', 'a[href*="/account"]',
                'button:has-text("Logout")', 'button:has-text("Sign out")',
                'a:has-text("Logout")', 'a:has-text("Sign out")',
                '.cart-icon', '[class*="cart"]',
                'a[href*="/products"]', 'a[href*="/shop"]',
                'text="Welcome"', 'text="My Account"',
            ]
            login_successful = False
            for sel in login_success_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=3000)
                    login_successful = True
                    print(f" ✅ Login confirmed via: {sel}")
                    break
                except Exception:
                    continue

            if login_successful:
                await notify("✅ Logged in successfully.")
            else:
                page_text_lower = (await page.evaluate("() => document.body.innerText")).lower()
                bad_creds = any(p in page_text_lower for p in [
                    "invalid credentials", "wrong password", "incorrect password", "login failed"
                ])
                if bad_creds:
                    await notify("❌ Login failed — check your store credentials.")
                    await page.wait_for_timeout(5000)
                    return

            # ── STEP 2: REGISTER (only if login truly failed) ──────────────
            if not login_successful:
                log_step(2, "Registering New User")
                await notify("📝 Account not found — registering…")
                await page.goto(f"{frontend_url}/register", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                inputs_visible = page.locator('input:visible')
                visible_count  = await inputs_visible.count()
                email_input     = None
                password_inputs = []
                text_inputs     = []

                for i in range(visible_count):
                    inp      = inputs_visible.nth(i)
                    inp_type = await inp.get_attribute("type") or "text"
                    inp_ph   = (await inp.get_attribute("placeholder") or "").lower()
                    inp_name = (await inp.get_attribute("name") or "").lower()
                    if inp_type == "email" or "email" in inp_ph or "email" in inp_name:
                        email_input = inp
                    elif inp_type == "password":
                        password_inputs.append(inp)
                    else:
                        text_inputs.append(inp)

                if len(text_inputs) >= 1 and email_input is not None:
                    await text_inputs[0].click(); await text_inputs[0].fill(user_info["name"])
                if email_input:
                    await email_input.click(); await email_input.fill(user_info["email"])
                else:
                    await smart_fill(page, user_info["email"], "email", types=("email",))

                if len(password_inputs) >= 2:
                    await password_inputs[0].click(); await password_inputs[0].fill(user_info["password"])
                    await password_inputs[1].click(); await password_inputs[1].fill(user_info["password"])
                elif len(password_inputs) == 1:
                    await password_inputs[0].click(); await password_inputs[0].fill(user_info["password"])

                for sel in ['button[type="submit"]', 'button:has-text("Register")',
                            'button:has-text("Sign up")', 'button:has-text("Create")']:
                    try:
                        btn = page.locator(sel)
                        if await btn.count() > 0 and await btn.first.is_visible():
                            await btn.first.click(); break
                    except Exception:
                        pass

                await page.wait_for_timeout(3000)

                if "login" in page.url.lower() or "sign" in page.url.lower():
                    inputs2 = page.locator('input:visible')
                    cnt2 = await inputs2.count()
                    for i in range(min(cnt2, 4)):
                        inp      = inputs2.nth(i)
                        inp_type = await inp.get_attribute("type") or "text"
                        if inp_type == "email" or "email" in (await inp.get_attribute("name") or "").lower():
                            await inp.fill(user_info["email"])
                        elif inp_type == "password":
                            await inp.fill(user_info["password"])
                    for sel in ['button[type="submit"]', 'button:has-text("Login")',
                                'button:has-text("Sign in")']:
                        try:
                            btn = page.locator(sel)
                            if await btn.count() > 0 and await btn.first.is_visible():
                                await btn.first.click(); break
                        except Exception:
                            pass
                    await page.wait_for_timeout(2500)

                for sel in login_success_selectors:
                    try:
                        await page.wait_for_selector(sel, timeout=3000)
                        login_successful = True; break
                    except Exception:
                        continue

            if "products" not in page.url and "shop" not in page.url:
                await page.goto(f"{frontend_url}/products", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

            # ── STEP 3: FIND PRODUCT ──────────────────────────────────────
            log_step(3, "Finding Product")
            await notify(f"🔍 Searching for '{product_name}'…")

            for selector in ['input[placeholder*="Search" i]', 'input[type="search"]',
                             'input[name="search"]', 'input[name="q"]']:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    await page.fill(selector, product_name)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(2000); break
                except Exception:
                    continue

            product_clicked = False
            try:
                await page.wait_for_selector(f'text={product_name}', timeout=3000)
                await page.click(f'text={product_name}')
                product_clicked = True
            except Exception:
                elements = await page.query_selector_all(
                    'h2, h3, h4, .product-title, .product-name, [class*="title"]'
                )
                for elem in elements:
                    text = await elem.text_content()
                    if text and product_name.lower() in text.lower():
                        await elem.click(); product_clicked = True; break

            if not product_clicked:
                first_product = await page.query_selector('.product-card, .product, .card, [class*="product"]')
                if first_product:
                    await first_product.click()

            await page.wait_for_timeout(2000)

            # ── STEP 4: ADD TO CART ───────────────────────────────────────
            log_step(4, "Adding to Cart")
            await notify("🛒 Adding product to cart…")

            for selector in ['button:has-text("Add to Cart")', 'button:has-text("ADD TO CART")',
                             'button[class*="add-to-cart"]', 'button[class*="addToCart"]',
                             'button:has-text("Add")']:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    await page.click(selector)
                    await page.wait_for_timeout(2000); break
                except Exception:
                    continue

            # ── STEP 5: GO TO CART ────────────────────────────────────────
            log_step(5, "Going to Cart")
            await notify("🛒 Opening cart…")

            cart_clicked = False
            for selector in ['a[href*="/cart"]', 'a[href="/cart"]', '.cart-icon',
                             '[class*="cart-icon"]', 'button:has-text("Cart")',
                             'a:has-text("Cart")', '[aria-label*="cart" i]']:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.click(); cart_clicked = True
                        await page.wait_for_timeout(2000); break
                except Exception:
                    continue

            if not cart_clicked:
                await page.goto(f"{frontend_url}/cart", wait_until="domcontentloaded")

            # ── STEP 6: CHECKOUT ──────────────────────────────────────────
            log_step(6, "Proceeding to Checkout")
            await notify("💳 Proceeding to checkout…")

            checkout_clicked = False
            for selector in ['button:has-text("Proceed to Checkout")', 'button:has-text("Checkout")',
                             'a:has-text("Proceed to Checkout")', 'a:has-text("Checkout")',
                             'button:has-text("Place Order")']:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    await page.click(selector)
                    checkout_clicked = True
                    await page.wait_for_timeout(2000); break
                except Exception:
                    continue

            if not checkout_clicked:
                await page.goto(f"{frontend_url}/checkout", wait_until="domcontentloaded")

            await page.wait_for_timeout(1500)
            await dump_inputs(page, "checkout page — before fill")

            # ── STEP 7: AUTO-FILL SHIPPING FIELDS ─────────────────────
            log_step(7, "Auto-filling name, email, phone")
            await notify("✍️ Auto-filling your name, email and phone number…")

            # Full Name
            await smart_fill(
                page, user_info["name"], "full name",
                names=("fullName", "full_name", "name", "full-name", "billing_name",
                       "shipping_name", "firstName", "first_name"),
                ids=("fullName", "full-name", "name", "billing-name", "firstName"),
                placeholders=("Full Name", "full name", "Your name", "Name", "First name"),
                autocompletes=("name", "given-name"),
                labels=("Full Name", "Name", "Your Name", "Billing Name", "Shipping Name", "First Name"),
            )
            await page.wait_for_timeout(200)

            # Email
            await smart_fill(
                page, user_info["email"], "email",
                names=("email", "emailAddress", "email_address"),
                ids=("email", "emailAddress"),
                types=("email",),
                placeholders=("Email", "email", "Email Address", "your@email.com"),
                autocompletes=("email",),
                labels=("Email", "Email Address", "E-mail"),
            )
            await page.wait_for_timeout(200)

            # Phone
            await smart_fill(
                page, user_info.get("phone", ""), "phone",
                names=("phone", "phoneNumber", "phone_number", "tel", "mobile"),
                ids=("phone", "phoneNumber", "tel"),
                types=("tel",),
                placeholders=("Phone", "phone", "Phone Number", "Mobile", "Telephone"),
                autocompletes=("tel",),
                labels=("Phone", "Phone Number", "Mobile", "Telephone", "Tel"),
            )
            await page.wait_for_timeout(200)

            # ── STEP 8: WAIT FOR USER TO FILL ADDRESS & ADVANCE ─────
            log_step(8, "Waiting for user to fill shipping address and advance to payment step")

            await notify(
                "✍️ Name, email and phone have been filled in. "
                "Please fill in your shipping address in the browser window, "
                "then click the Continue / Next button to reach the payment step.",
                msg_type="bot_status"
            )

            print("⏳ Waiting for user to fill address and advance to Step 2 (payment)…")

            payment_step_selectors = [
                'input[placeholder*="card" i]',
                'input[placeholder*="Card" i]',
                'input[name*="card" i]',
                'input[id*="card" i]',
                '[class*="card-element"]',
                '[class*="cardElement"]',
                '[class*="stripe"]',
                'iframe[name*="stripe"]',
                'iframe[src*="stripe"]',
                'text="Payment Information"',
                'text="Card Details"',
                'text="Card Information"',
                'text="Payment Details"',
                'h2:has-text("Payment")',
                'h3:has-text("Payment")',
                '[data-testid*="payment"]',
            ]

            step2_detected = False
            for _ in range(300):  # poll up to 10 minutes
                for sel in payment_step_selectors:
                    try:
                        elem = page.locator(sel)
                        if await elem.count() > 0 and await elem.first.is_visible():
                            print(f" ✅ Payment step detected via: {sel}")
                            step2_detected = True
                            break
                    except Exception:
                        pass
                if step2_detected:
                    break
                await page.wait_for_timeout(2000)

            # ── STEP 9: NOTIFY USER TO FILL CARD DETAILS AND CLICK PAY ─────
            if step2_detected:
                await notify(
                    "💳 Payment step detected! Please enter your card details in the browser, "
                    "then click the 'Pay' button to complete your order. "
                    "The bot will automatically detect the order confirmation.",
                    msg_type="bot_status"
                )
            else:
                await notify(
                    "💳 Please fill in your card details in the browser window, "
                    "then click the 'Pay' button to complete your order.",
                    msg_type="bot_status"
                )

            print("⏳ Waiting for user to complete payment and for order confirmation page...")

            # ── STEP 10: WAIT FOR ORDER CONFIRMATION PAGE ─────────────────
            confirmation_selectors = [
                'text="Order Confirmed"', 'text="Order Confirmation"',
                'text="Thank you for your purchase"', 'text="Thank you for your order"',
                'text="successfully placed"', 'text="Order placed"',
                'text="Payment successful"', 'text="Payment Successful"',
                '.order-confirmation', '.order-success',
                '[class*="success"]', '[class*="confirmation"]',
                'h1:has-text("Order")', 'h2:has-text("Order")',
                '.order-id', '.order-number', 'text="Order #"',
            ]

            confirmed = False
            start_time = time.time()
            timeout_secs = 600  # 10 minutes

            while not confirmed and (time.time() - start_time) < timeout_secs:
                for selector in confirmation_selectors:
                    try:
                        await page.wait_for_selector(selector, timeout=2000)
                        confirmed = True
                        break
                    except Exception:
                        continue
                if not confirmed:
                    await page.wait_for_timeout(2000)

            if not confirmed:
                await notify("⏱️ Timed out waiting for order confirmation (10 min). Please try again.")
                print("❌ Order confirmation timed out")
                return

            # ── STEP 11: EXTRACT CONFIRMATION DETAILS ─────────────────────
            log_step(11, "Extracting Order Details")
            page_text = await page.evaluate("() => document.body.innerText")
            print(f"📄 Confirmation (first 500):\n{page_text[:500]}")

            delivery_date = None
            order_id      = None

            oid_match = re.search(
                r"(?:order\s*(?:id|#|number)[:\s#]*|#)(\w+)",
                page_text, re.IGNORECASE
            )
            if oid_match:
                order_id = oid_match.group(1)

            delivery_keywords = ["estimated delivery", "delivery date", "expected delivery",
                                  "arrives", "arrival", "ships by", "deliver by", "delivery by"]
            lines = page_text.splitlines()
            for i, line in enumerate(lines):
                if any(kw in line.lower() for kw in delivery_keywords):
                    combined = line + (" " + lines[i + 1] if i + 1 < len(lines) else "")
                    parsed = _parse_delivery_date(combined)
                    if parsed:
                        delivery_date = parsed; break

            if not delivery_date:
                parsed = _parse_delivery_date(page_text)
                if parsed:
                    delivery_date = parsed

            if not delivery_date:
                delivery_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")

            # ── STEP 12: POST CONFIRMATION TO BACKEND ─────────────────────
            log_step(12, "Posting Confirmation to Backend")
            try:
                async with httpx.AsyncClient() as client:
                    payload = {
                        "email": user_info["email"],
                        "product_name": product_name,
                        "delivery_date": delivery_date,
                    }
                    if order_id:
                        payload["order_id"] = str(order_id)

                    resp = await client.post(
                        "http://localhost:8000/order-confirm",
                        json=payload, timeout=10.0
                    )
                    print(f"✅ Backend: {resp.status_code}")
            except Exception as e:
                print(f"❌ Error posting confirmation: {e}")

            # ── FINAL SUCCESS MESSAGE ─────────────────────────────────────
            await notify(
                f"🎉 Order placed successfully! "
                + (f". Order ID: {order_id}" if order_id else "."),
                msg_type="order_confirmation"
            )

            print("\n" + "="*50 + "\n ORDER COMPLETED SUCCESSFULLY\n" + "="*50)
            await page.wait_for_timeout(10000)

        except Exception as e:
            import traceback; traceback.print_exc()
            await notify(f"❌ Order bot error: {str(e)[:120]}")
            await page.wait_for_timeout(8000)
        finally:
            try:
                await browser.close()
                print("\n✅ Browser closed")
            except Exception:
                pass