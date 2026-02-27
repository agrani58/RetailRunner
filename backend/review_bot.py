"""
review_bot.py — v2

Mirrors order_bot.py approach exactly:
  1. Login to the store
  2. Navigate to the product page (find the product)
  3. Add to cart → Checkout → reach the Order Confirmation page
     (which contains the review form in your store's UI)
  4. On the confirmation page, click the stars and fill the review textarea
  5. Click "Submit Review"
  6. Call /mark-reviewed on success

Fallback: If the order_reference is provided (e.g. "44"), navigate directly
to /order-success/{order_reference} or /orders/{order_reference} first,
since the review widget lives on the post-purchase confirmation page.
"""

import asyncio
import logging
import re
import aiohttp
from typing import Callable, Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger("review_bot")

MARK_REVIEWED_URL = "http://localhost:8000/mark-reviewed"

# ── Known store port mapping (same as order_bot / review_bot v1) ──────────────
FRONTEND_TO_API = {
    "100.30.70.54":   "http://100.30.70.54:5002",
    "44.219.130.221": "http://44.219.130.221:5001",
    "98.87.208.115":  "http://98.87.208.115:5000",
}


async def _safe_notify(notify_callback: Optional[Callable], msg: str):
    if notify_callback:
        try:
            await notify_callback(msg)
        except Exception:
            pass


def _api_base(frontend_url: str) -> str:
    m = re.search(r"([\d.]+)", frontend_url)
    if m and m.group(1) in FRONTEND_TO_API:
        return FRONTEND_TO_API[m.group(1)]
    return frontend_url.rstrip("/")


def log_step(step_num, description):
    print(f"\n{'='*60}\nSTEP {step_num}: {description}\n{'='*60}")


# ─────────────────────────────────────────────────────────────────────────────
# Smart fill helper (copied from order_bot for consistency)
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Try direct API login + review submission (fast path)
# ─────────────────────────────────────────────────────────────────────────────

async def _api_try(frontend_url: str, product_name: str,
                   email: str, password: str,
                   rating: int, review_text: str) -> bool:
    """Try REST API login → find product → POST review. Returns True on success."""
    api_base = _api_base(frontend_url)
    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Step A: Login
            token = None
            for endpoint in [
                f"{api_base}/api/login",
                f"{api_base}/api/auth/login",
                f"{api_base}/login",
                f"{api_base}/auth/login",
            ]:
                try:
                    async with session.post(endpoint, json={"email": email, "password": password}) as resp:
                        if resp.status in (200, 201):
                            data = await resp.json()
                            token = (
                                data.get("token") or data.get("access_token") or
                                data.get("accessToken") or data.get("jwt") or
                                (data.get("data") or {}).get("token") or
                                (data.get("user") or {}).get("token")
                            )
                            if token:
                                logger.info("[ReviewBot-API] Login ✅ via %s", endpoint)
                                break
                            else:
                                logger.debug("[ReviewBot-API] No token in response keys: %s", list(data.keys()))
                except Exception as e:
                    logger.debug("[ReviewBot-API] Login %s error: %s", endpoint, e)

            if not token:
                logger.warning("[ReviewBot-API] Login failed — no token")
                return False

            headers = {"Authorization": f"Bearer {token}"}

            # Step B: Find product_id
            product_id = None
            for endpoint in [
                f"{api_base}/api/products",
                f"{api_base}/api/secure/products",
                f"{api_base}/products",
            ]:
                try:
                    async with session.get(endpoint, headers=headers) as resp:
                        if resp.status == 200:
                            products = await resp.json()
                            if isinstance(products, dict):
                                products = products.get("products") or products.get("data") or []
                            for p in products:
                                pname = p.get("name", "")
                                if (pname.lower() == product_name.lower() or
                                        product_name.lower() in pname.lower()):
                                    product_id = p.get("id") or p.get("product_id")
                                    logger.info("[ReviewBot-API] Found product id=%s", product_id)
                                    break
                            if product_id is not None:
                                break
                except Exception as e:
                    logger.debug("[ReviewBot-API] Products %s error: %s", endpoint, e)

            if product_id is None:
                logger.warning("[ReviewBot-API] Product not found")
                return False

            # Step C: Submit review
            payload = {"product_id": product_id, "rating": rating, "comment": review_text, "review": review_text}
            for endpoint in [
                f"{api_base}/api/reviews",
                f"{api_base}/reviews",
                f"{api_base}/api/products/{product_id}/reviews",
            ]:
                try:
                    async with session.post(endpoint, json=payload, headers=headers) as resp:
                        if resp.status in (200, 201):
                            logger.info("[ReviewBot-API] ✅ Review submitted via %s", endpoint)
                            return True
                        else:
                            body = await resp.text()
                            logger.debug("[ReviewBot-API] %s → HTTP %s: %s", endpoint, resp.status, body[:200])
                except Exception as e:
                    logger.debug("[ReviewBot-API] Review %s error: %s", endpoint, e)

    except Exception as e:
        logger.warning("[ReviewBot-API] Exception: %s", e)

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Browser automation — mirrors order_bot exactly
# ─────────────────────────────────────────────────────────────────────────────

async def _browser_submit_review(
    frontend_url: str,
    product_name: str,
    email: str,
    password: str,
    rating: int,
    review_text: str,
    order_reference: Optional[str] = None,
    notify_callback: Optional[Callable] = None,
) -> bool:

    async def notify(msg: str):
        await _safe_notify(notify_callback, msg)

    print(f"\n🚀 Review bot browser starting for '{product_name}' on {frontend_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=200)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        page.set_default_timeout(30000)

        try:
            # ── STEP 1: LOGIN ─────────────────────────────────────────────
            log_step(1, "Login")
            await notify("🔐 Logging into the store…")
            await page.goto(f"{frontend_url}/login", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Dump inputs for debugging
            inputs = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('input')).map(el => ({
                    type: el.type, name: el.name, placeholder: el.placeholder, visible: el.offsetParent !== null
                }));
            }""")
            print(f"📋 Login inputs: {inputs}")

            email_filled = await smart_fill(
                page, email, "email",
                names=("email", "Email", "user_email", "username"),
                ids=("email", "user-email", "login-email"),
                types=("email",),
                placeholders=("email", "e-mail", "your email", "Enter email"),
                autocompletes=("email", "username"),
                labels=("Email", "E-mail", "Email address", "Username"),
            )
            pw_filled = await smart_fill(
                page, password, "password",
                names=("password", "Password", "pass"),
                ids=("password", "user-password"),
                types=("password",),
                placeholders=("password", "Password", "Enter password"),
                autocompletes=("current-password",),
                labels=("Password", "Pass"),
            )

            # Positional fallback
            if not email_filled or not pw_filled:
                print("⚠️ Labeled fill failed — positional fallback")
                vis = page.locator('input:visible')
                cnt = await vis.count()
                if cnt >= 2:
                    await vis.nth(0).click(); await vis.nth(0).fill(email)
                    await vis.nth(1).click(); await vis.nth(1).fill(password)

            for sel in ['button[type="submit"]', 'button:has-text("Login")',
                        'button:has-text("Sign in")', 'button:has-text("Log in")',
                        'input[type="submit"]']:
                try:
                    btn = page.locator(sel)
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.click(); break
                except Exception:
                    pass

            await page.wait_for_timeout(3000)

            # Confirm login
            login_ok = False
            for sel in ['button:has-text("Logout")', 'a:has-text("Logout")',
                        'button:has-text("Sign out")', '[class*="cart"]',
                        'a[href*="/products"]', 'a[href*="/shop"]', 'text="Welcome"']:
                try:
                    await page.wait_for_selector(sel, timeout=3000)
                    login_ok = True
                    print(f" ✅ Login confirmed via: {sel}")
                    break
                except Exception:
                    continue

            if not login_ok:
                page_text = (await page.evaluate("() => document.body.innerText")).lower()
                if any(w in page_text for w in ["invalid", "wrong password", "failed"]):
                    await notify("❌ Login failed — wrong credentials")
                    return False
                # If no login error shown, assume it worked (some SPAs don't show typical indicators)
                print("⚠️ Login indicator not found, continuing anyway")

            await notify("✅ Logged in successfully.")

            # ── STEP 2: NAVIGATE TO ORDER CONFIRMATION PAGE ───────────────
            # Strategy A: Go directly to order-success / order page by reference ID
            review_form_found = False

            if order_reference:
                log_step(2, f"Navigating to order confirmation page (order #{order_reference})")
                await notify(f"📋 Navigating to order #{order_reference} confirmation page…")

                candidate_urls = [
                    f"{frontend_url}/order-success/{order_reference}",
                    f"{frontend_url}/order-confirm/{order_reference}",
                    f"{frontend_url}/orders/{order_reference}",
                    f"{frontend_url}/order/{order_reference}",
                    f"{frontend_url}/checkout/success/{order_reference}",
                    f"{frontend_url}/confirmation/{order_reference}",
                ]

                for url in candidate_urls:
                    print(f" 🔗 Trying: {url}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded")
                        await page.wait_for_timeout(2000)

                        page_text = (await page.evaluate("() => document.body.innerText")).lower()

                        # Check if we landed on a useful page (not 404/error/login)
                        is_404 = any(w in page_text for w in ["404", "not found", "page doesn't exist"])
                        is_login = "login" in page.url.lower() or "sign in" in page_text[:100]

                        if is_404 or is_login:
                            print(f" ❌ Not useful: {url}")
                            continue

                        # Check for review form elements
                        for sel in [
                            'text="Your Rating:"',
                            'text="Leave a Review"',
                            'text="Submit Review"',
                            'button:has-text("Submit Review")',
                            '[class*="review"]',
                        ]:
                            try:
                                el = page.locator(sel)
                                if await el.count() > 0:
                                    print(f" ✅ Review form found at {url} via '{sel}'")
                                    review_form_found = True
                                    break
                            except Exception:
                                pass

                        if review_form_found:
                            break

                        # Also check if product name is on page (order details page)
                        if product_name.lower() in page_text:
                            print(f" ✅ Product found on page: {url}")
                            review_form_found = True
                            break

                    except Exception as e:
                        print(f" ⚠️ Error navigating to {url}: {e}")
                        continue

            # Strategy B: Go through products → find product → trigger post-purchase review
            if not review_form_found:
                log_step(3, "Finding product page directly")
                await notify(f"🔍 Looking for '{product_name}' review section…")

                # Go to products page
                await page.goto(f"{frontend_url}/products", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                # Search for product
                for selector in ['input[placeholder*="Search" i]', 'input[type="search"]',
                                  'input[name="search"]', 'input[name="q"]']:
                    try:
                        await page.wait_for_selector(selector, timeout=2000)
                        await page.fill(selector, product_name)
                        await page.keyboard.press("Enter")
                        await page.wait_for_timeout(2000)
                        break
                    except Exception:
                        continue

                # Click on the product
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
                            await elem.click()
                            product_clicked = True
                            break

                if product_clicked:
                    await page.wait_for_timeout(2000)
                    # Check for review section on product page
                    for sel in ['text="Leave a Review"', 'text="Write a Review"',
                                 'text="Your Rating:"', '[class*="review-form"]']:
                        try:
                            el = page.locator(sel)
                            if await el.count() > 0:
                                review_form_found = True
                                break
                        except Exception:
                            pass

            # Strategy C: Re-purchase flow (like order_bot) to reach confirmation page with review
            if not review_form_found:
                log_step(4, "Re-purchase flow to reach order confirmation with review form")
                await notify("🛒 Using purchase flow to reach review form…")

                # Go to products
                await page.goto(f"{frontend_url}/products", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                # Find and click product
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
                            await elem.click()
                            product_clicked = True
                            break
                await page.wait_for_timeout(2000)

                # Add to cart
                await notify("🛒 Adding to cart…")
                for selector in ['button:has-text("Add to Cart")', 'button:has-text("ADD TO CART")',
                                  'button[class*="add-to-cart"]', 'button:has-text("Add")']:
                    try:
                        await page.wait_for_selector(selector, timeout=2000)
                        await page.click(selector)
                        await page.wait_for_timeout(2000)
                        break
                    except Exception:
                        continue

                # Go to cart
                cart_clicked = False
                for selector in ['a[href*="/cart"]', '.cart-icon', '[class*="cart-icon"]',
                                  'button:has-text("Cart")', 'a:has-text("Cart")',
                                  '[aria-label*="cart" i]']:
                    try:
                        elem = await page.query_selector(selector)
                        if elem:
                            await elem.click()
                            cart_clicked = True
                            await page.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue
                if not cart_clicked:
                    await page.goto(f"{frontend_url}/cart", wait_until="domcontentloaded")

                # Checkout
                await notify("💳 Proceeding to checkout…")
                for selector in ['button:has-text("Proceed to Checkout")', 'button:has-text("Checkout")',
                                  'a:has-text("Checkout")', 'button:has-text("Place Order")']:
                    try:
                        await page.wait_for_selector(selector, timeout=2000)
                        await page.click(selector)
                        await page.wait_for_timeout(2000)
                        break
                    except Exception:
                        continue

                # Auto-fill shipping fields
                await notify("✍️ Filling shipping details…")
                await smart_fill(page, email, "full name / email fallback",
                                 names=("name", "fullName", "full_name"),
                                 placeholders=("Full Name", "Your name", "Name"),
                                 labels=("Full Name", "Name"))
                await smart_fill(page, email, "email",
                                 names=("email",), types=("email",),
                                 placeholders=("Email", "your@email.com"),
                                 labels=("Email",))

                # Notify user to fill rest and pay
                await notify(
                    "✍️ Please fill in your shipping address and complete payment in the browser. "
                    "The bot will detect the order confirmation page with the review form automatically.",
                    # msg_type handled by caller
                )

                # Wait for order confirmation page
                confirmation_selectors = [
                    'text="Order Confirmed"', 'text="Order Confirmation"',
                    'text="Thank you for your purchase"', 'text="successfully placed"',
                    'text="Leave a Review"', 'text="Your Rating:"',
                    '.order-confirmation', '[class*="success"]',
                    'h1:has-text("Order")', 'h2:has-text("Order")',
                ]

                import time
                start = time.time()
                while time.time() - start < 600:
                    for sel in confirmation_selectors:
                        try:
                            await page.wait_for_selector(sel, timeout=2000)
                            review_form_found = True
                            print(f" ✅ Confirmation/review page detected via: {sel}")
                            break
                        except Exception:
                            continue
                    if review_form_found:
                        break
                    await page.wait_for_timeout(2000)

            if not review_form_found:
                await notify("❌ Could not find the review form. Please try again.")
                return False

            # ── STEP 5: FILL REVIEW FORM ──────────────────────────────────
            log_step(5, "Filling review form")
            await notify("⭐ Filling in your review…")
            await page.wait_for_timeout(1000)

            # Scroll to review section
            for sel in ['text="Leave a Review"', 'text="Your Rating:"',
                        'text="Write a Review"', '[class*="review"]']:
                try:
                    el = page.locator(sel)
                    if await el.count() > 0:
                        await el.first.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        break
                except Exception:
                    pass

            await page.wait_for_timeout(500)

            # ── Click stars ───────────────────────────────────────────────
            # Your store uses: <span>★</span> or <span>☆</span> spans with onClick
            # Strategy: Use JS to find star spans near "Your Rating:" label and click Nth
            star_clicked = False

            print(f" 🌟 Trying to click star {rating}")

            # JS approach: find star spans and click the correct one
            star_result = await page.evaluate("""(targetRating) => {
                // Find all star character spans
                const allSpans = Array.from(document.querySelectorAll('span'));
                const starSpans = allSpans.filter(s => {
                    const t = s.textContent.trim();
                    return t === '★' || t === '☆';
                });

                console.log('Total star spans found:', starSpans.length);

                // Group by vertical position (y-coordinate)
                const groups = {};
                starSpans.forEach(s => {
                    const rect = s.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) return;
                    const yKey = Math.round(rect.top / 15) * 15;
                    if (!groups[yKey]) groups[yKey] = [];
                    groups[yKey].push({ el: s, x: rect.left, y: rect.top, rect });
                });

                // Find a group of 5 stars (the interactive rating widget)
                let targetGroup = null;
                const groupKeys = Object.keys(groups).sort((a, b) => Number(a) - Number(b));
                
                for (const key of groupKeys) {
                    const g = groups[key].sort((a, b) => a.x - b.x);
                    if (g.length === 5) {
                        // Check if cursor is pointer (interactive)
                        const style = window.getComputedStyle(g[0].el);
                        if (style.cursor === 'pointer') {
                            targetGroup = g;
                            break;
                        }
                        // Keep as candidate even without pointer cursor
                        if (!targetGroup) targetGroup = g;
                    }
                }

                // Fallback: any group >= 4 stars
                if (!targetGroup) {
                    for (const key of groupKeys) {
                        const g = groups[key].sort((a, b) => a.x - b.x);
                        if (g.length >= 4) {
                            targetGroup = g.slice(0, 5);
                            break;
                        }
                    }
                }

                if (!targetGroup || targetGroup.length < targetRating) {
                    return { found: false, totalSpans: starSpans.length, groups: groupKeys.length };
                }

                const target = targetGroup[targetRating - 1];
                target.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                
                // Fire multiple events to ensure React state updates
                target.el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                target.el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                target.el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                target.el.click();

                return {
                    found: true,
                    groupSize: targetGroup.length,
                    clickedIndex: targetRating - 1,
                    text: target.el.textContent.trim(),
                    x: target.rect.left,
                    y: target.rect.top
                };
            }""", rating)

            print(f" 🌟 Star JS result: {star_result}")

            if star_result and star_result.get("found"):
                star_clicked = True
                await page.wait_for_timeout(500)
                print(f" ✅ Star {rating} clicked via JS")
            
            # Playwright fallback: use bounding box of "Your Rating:" label
            if not star_clicked:
                print(" ⚠️ JS click failed, trying Playwright locator approach")
                try:
                    # Try clicking span stars directly with Playwright
                    star_spans = page.locator('span').filter(has_text=re.compile(r'^[★☆]$'))
                    count = await star_spans.count()
                    print(f" Found {count} star spans via Playwright")
                    
                    if count >= 5:
                        # Find groups of 5 consecutive stars
                        # Click the one at index (rating - 1) within the last group of 5
                        # that's visible
                        visible_stars = []
                        for i in range(count):
                            s = star_spans.nth(i)
                            try:
                                if await s.is_visible():
                                    box = await s.bounding_box()
                                    if box and box["width"] > 0:
                                        visible_stars.append((i, s, box))
                            except Exception:
                                pass

                        print(f" Visible star spans: {len(visible_stars)}")

                        if len(visible_stars) >= 5:
                            # Use the last group of 5 (likely the interactive review widget)
                            group = visible_stars[-5:]
                            # Sort by x position
                            group.sort(key=lambda x: x[2]["x"])
                            target_star = group[rating - 1][1]
                            await target_star.scroll_into_view_if_needed()
                            await target_star.click()
                            star_clicked = True
                            await page.wait_for_timeout(500)
                            print(f" ✅ Star {rating} clicked via Playwright locator")

                except Exception as e:
                    print(f" ⚠️ Playwright star click error: {e}")

            # Mouse coordinate fallback using "Your Rating:" label
            if not star_clicked:
                print(" ⚠️ Trying coordinate-based star click")
                try:
                    label = page.locator('text="Your Rating:"')
                    if await label.count() > 0:
                        box = await label.first.bounding_box()
                        if box:
                            # Stars are typically 20-28px wide, right of label
                            star_x = box["x"] + box["width"] + (rating - 0.5) * 26
                            star_y = box["y"] + box["height"] / 2
                            await page.mouse.click(star_x, star_y)
                            star_clicked = True
                            await page.wait_for_timeout(500)
                            print(f" ✅ Star {rating} clicked via coordinates")
                except Exception as e:
                    print(f" ⚠️ Coordinate fallback error: {e}")

            if not star_clicked:
                print(" ⚠️ Could not click stars — proceeding anyway")

            await page.wait_for_timeout(600)

            # ── Fill review textarea ──────────────────────────────────────
            if review_text:
                print(f" ✍️ Filling review text: '{review_text[:60]}…'")
                filled = await smart_fill(
                    page, review_text, "review text",
                    names=("review", "comment", "text", "reviewText", "review_text"),
                    ids=("review", "comment", "reviewText"),
                    placeholders=(
                        "Share your experience",
                        "experience",
                        "review",
                        "comment",
                        "thoughts",
                        "Tell us",
                    ),
                    labels=("Review", "Your Review", "Comment", "Your review"),
                    is_textarea=True,
                )
                if not filled:
                    # Nuclear fallback: first visible empty textarea
                    ta = page.locator("textarea:visible")
                    cnt = await ta.count()
                    for i in range(cnt):
                        try:
                            t = ta.nth(i)
                            if await t.is_visible():
                                current = await t.input_value()
                                if not current.strip():
                                    await t.scroll_into_view_if_needed()
                                    await t.click()
                                    await t.fill(review_text)
                                    print(f" ✅ Filled review via textarea #{i}")
                                    filled = True
                                    break
                        except Exception:
                            pass

            await page.wait_for_timeout(500)

            # ── Click Submit Review ───────────────────────────────────────
            log_step(6, "Submitting review")
            await notify("📤 Submitting review…")

            submitted = False
            for sel in [
                'button:has-text("Submit Review")',
                'button:has-text("Submit")',
                'button:has-text("Post Review")',
                'button:has-text("Post")',
                'input[type="submit"]',
                'button[type="submit"]',
            ]:
                try:
                    btn = page.locator(sel)
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.scroll_into_view_if_needed()
                        await btn.first.click()
                        await page.wait_for_timeout(2500)
                        submitted = True
                        print(f" ✅ Clicked submit via: {sel}")
                        break
                except Exception:
                    pass

            if not submitted:
                print(" ⚠️ Could not find Submit Review button")
                # Take screenshot for debugging
                try:
                    await page.screenshot(path="/tmp/review_debug.png")
                    print(" 📸 Debug screenshot saved to /tmp/review_debug.png")
                except Exception:
                    pass
                return False

            # ── Verify success ────────────────────────────────────────────
            for sel in [
                'text="Review Submitted"',
                'text="Thank you"',
                'text="Review submitted"',
                'text="successfully"',
                '[class*="success"]',
            ]:
                try:
                    await page.wait_for_selector(sel, timeout=4000)
                    print(f" ✅ Success confirmed via: {sel}")
                    await page.wait_for_timeout(2000)
                    return True
                except Exception:
                    pass

            # No explicit error = assume success
            body = (await page.evaluate("() => document.body.innerText")).lower()
            if not any(w in body for w in ["error", "failed", "invalid", "wrong"]):
                print(" ✅ No error detected — assuming review submitted")
                await page.wait_for_timeout(2000)
                return True

            print(" ❌ Error detected on page after submission")
            return False

        except Exception as e:
            import traceback
            traceback.print_exc()
            await notify(f"❌ Review bot error: {str(e)[:120]}")
            return False

        finally:
            try:
                await page.wait_for_timeout(3000)
                await browser.close()
                print("\n✅ Review bot browser closed")
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

async def submit_review_bot(
    frontend_url: str,
    product_name: str,
    user_info: dict,
    rating: int,
    review_text: str,
    user_id: int,
    order_id: int,
    notify_callback: Optional[Callable] = None,
    order_reference: Optional[str] = None,
) -> bool:
    """
    Submit a product review to the third-party store.

    Strategy 1: Direct REST API (fast, no browser)
    Strategy 2: Browser automation navigating to order confirmation page
                (same page where the review form lives in your store)
    """
    logger.info("[ReviewBot] 🤖 Starting for order_id=%s, order_reference=%s, product='%s'",
                order_id, order_reference, product_name)

    email    = user_info.get("email", "")
    password = user_info.get("password", "")

    if not email or not password:
        logger.error("[ReviewBot] ❌ Missing credentials")
        await _safe_notify(notify_callback, "❌ Store email and password are required.")
        return False

    success = False

    # ── Strategy 1: Direct API ────────────────────────────────────────────
    await _safe_notify(notify_callback, "🔐 Trying direct API submission…")
    logger.info("[ReviewBot] 🌐 Trying API strategy")
    try:
        success = await _api_try(
            frontend_url=frontend_url,
            product_name=product_name,
            email=email,
            password=password,
            rating=rating,
            review_text=review_text,
        )
    except Exception as e:
        logger.warning("[ReviewBot] API exception: %s", e)
        success = False

    # ── Strategy 2: Browser ───────────────────────────────────────────────
    if not success:
        logger.info("[ReviewBot] 🖥️ API failed — browser automation")
        await _safe_notify(notify_callback, "🖥️ Opening browser to submit review…")
        try:
            success = await _browser_submit_review(
                frontend_url=frontend_url,
                product_name=product_name,
                email=email,
                password=password,
                rating=rating,
                review_text=review_text,
                order_reference=order_reference,
                notify_callback=notify_callback,
            )
        except Exception as e:
            logger.error("[ReviewBot] Browser exception: %s", e, exc_info=True)
            success = False

    # ── Mark reviewed ─────────────────────────────────────────────────────
    if success:
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(MARK_REVIEWED_URL, json={"order_id": order_id})
            logger.info("[ReviewBot] ✅ Order %s marked reviewed", order_id)
            await _safe_notify(notify_callback, "✅ Review posted successfully!")
        except Exception as e:
            logger.error("[ReviewBot] Failed to mark reviewed: %s", e)
            await _safe_notify(notify_callback, "✅ Review posted! (status update failed)")
    else:
        await _safe_notify(notify_callback,
                           "⚠️ Could not submit review automatically. Please try on the store website.")

    return success