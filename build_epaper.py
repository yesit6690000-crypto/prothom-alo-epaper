import os
import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from ebooklib import epub

RAW_COOKIE_JSON = os.getenv("EPAPER_COOKIE_JSON", "").strip()

async def main():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_epaper_{today_str}.epub"

    if not RAW_COOKIE_JSON:
        raise Exception("EPAPER_COOKIE_JSON secret is missing from GitHub Secrets.")

    try:
        cookies = json.loads(RAW_COOKIE_JSON)
    except Exception as e:
        raise Exception(f"Failed to parse EPAPER_COOKIE_JSON: {e}")

    page_images = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )

        formatted_cookies = []
        for c in cookies:
            cookie_dict = {
                "name": c.get("name"),
                "value": c.get("value"),
                "domain": c.get("domain", ".prothomalo.com"),
                "path": c.get("path", "/")
            }
            if cookie_dict["domain"] and not cookie_dict["domain"].startswith("http"):
                formatted_cookies.append(cookie_dict)

        await context.add_cookies(formatted_cookies)
        page = await context.new_page()

        # Intercept network image streams (> 30KB to bypass logos/wireframes)
        async def handle_response(response):
            url = response.url
            content_type = response.headers.get("content-type", "")
            if "image" in content_type and response.status == 200:
                try:
                    body = await response.body()
                    if len(body) > 30000 and url not in page_images:
                        page_images[url] = body
                        print(f"[+] Intercepted page scan ({len(body)} bytes)")
                except Exception:
                    pass

        page.on("response", handle_response)

        print("[*] Opening ePaper portal in headless browser...")
        await page.goto("https://epaper.prothomalo.com/", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(4000)

        # Flip through pages to trigger network loading of all broadsheet scans
        for page_idx in range(16):
            await page.keyboard.press("ArrowRight")
            await page.wait_for_timeout(1500)

        await browser.close()

    image_bytes_list = list(page_images.values())
    print(f"[*] Total valid broadsheet scans captured: {len(image_bytes_list)}")

    if not image_bytes_list:
        raise Exception("No ePaper page images captured. Please refresh your browser login cookie.")

    book = epub.EpubBook()
    book.set_identifier(f"prothom-alo-epaper-{today_str}")
    book.set_title(f"প্রথম আলো ইপেপার - {today_str}")
    book.set_language("bn")
    book.add_author("দৈনিক প্রথম আলো")

    style = '''
    body { background-color: #000; margin: 0; padding: 0; text-align: center; }
    div.page { page-break-after: always; height: 100vh; display: flex; align-items: center; justify-content: center; }
    img { max-width: 100%; max-height: 100%; height: auto; display: block; margin: auto; }
    '''
    css_item = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=style)
    book.add_item(css_item)

    chapters = []
    spine = ['nav']

    for i, img_bytes in enumerate(image_bytes_list, start=1):
        img_item = epub.EpubItem(
            uid=f"page_img_{i}",
            file_name=f"images/page_{i}.jpg",
            media_type="image/jpeg",
            content=img_bytes
        )
        book.add_item(img_item)

        chapter = epub.EpubHtml(
            title=f"পাতা {i}",
            file_name=f"page_{i}.xhtml",
            lang="bn"
        )
        chapter.content = f"""
        <html>
        <head><title>পাতা {i}</title><link rel="stylesheet" href="style.css" type="text/css"/></head>
        <body>
            <div class="page"><img src="images/page_{i}.jpg" alt="Page {i}"/></div>
        </body>
        </html>
        """
        chapter.add_item(css_item)
        book.add_item(chapter)
        chapters.append(chapter)
        spine.append(chapter)

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] ePaper EPUB generated successfully: {output_filename}")

if __name__ == "__main__":
    asyncio.run(main())
