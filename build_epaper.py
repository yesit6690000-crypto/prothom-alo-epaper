import os
import re
import time
import requests
from datetime import datetime
from PIL import Image
from playwright.sync_api import sync_playwright
import ebooklib
from ebooklib import epub

def extract_epaper_pages():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_epub = f"prothom_alo_epaper_{today_str}.epub"
    temp_dir = "scraped_pages"
    os.makedirs(temp_dir, exist_ok=True)
    
    captured_images = []

    print(f"[*] Starting scraper for date: {today_str}")

    with sync_playwright() as p:
        # Launch headless browser with realistic desktop profile
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 2880},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Intercept and record high-res image requests directly from network
        found_urls = []
        def intercept_response(response):
            # Capture actual page raster scans loaded by the viewer
            url = response.url
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png']) and ('page' in url.lower() or 'epaper' in url.lower() or 'edition' in url.lower()):
                if url not in found_urls and 'thumb' not in url.lower() and 'icon' not in url.lower():
                    found_urls.append(url)

        page.on("response", intercept_response)

        target_url = "https://epaper.prothomalo.com/"
        print(f"[*] Navigating to: {target_url}")
        
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(7000) # Give viewer JS time to mount
        except Exception as e:
            print(f"[!] Navigation notice: {e}")

        # Determine total pages or loop through standard 12-16 broadsheet pages
        max_pages = 16
        for page_num in range(1, max_pages + 1):
            print(f"[*] Processing page {page_num}...")
            img_filename = os.path.join(temp_dir, f"page_{page_num:02d}.jpg")

            # Strategy 1: If network interception caught pages, use direct download
            # Strategy 2: High-resolution viewport element clip
            viewer_container = page.locator("canvas, .pageContainer, #pageContainer, .magazine-viewport, .carousel-item.active, img.page-image").first

            page.wait_for_timeout(2000)

            if viewer_container.count() > 0 and viewer_container.is_visible():
                viewer_container.screenshot(path=img_filename, quality=90, type="jpeg")
            else:
                # Fallback: Capture central desktop viewport
                page.screenshot(path=img_filename, quality=90, type="jpeg")

            captured_images.append(img_filename)

            # Advance to next page
            # Covers common selector conventions across epaper updates
            next_buttons = [
                page.locator("[aria-label*='Next']"),
                page.locator("button.next"),
                page.locator(".btn-next"),
                page.locator(".fa-chevron-right"),
                page.locator(".right-arrow"),
                page.locator("#next")
            ]

            clicked = False
            for btn in next_buttons:
                if btn.count() > 0 and btn.first.is_visible():
                    try:
                        btn.first.click()
                        clicked = True
                        page.wait_for_timeout(3500)
                        break
                    except Exception:
                        continue

            if not clicked:
                # Alternatively trigger right arrow keyboard event
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(3000)

        browser.close()

    if not captured_images:
        raise RuntimeError("Failed to capture any pages from ePaper.")

    # Build Fixed-Layout EPUB
    print(f"[*] Compiling {len(captured_images)} pages into EPUB: {output_epub}")
    book = epub.EpubBook()
    book.set_identifier(f"prothom-alo-epaper-{today_str}")
    book.set_title(f"দৈনিক প্রথম আলো - {today_str}")
    book.set_language("bn")
    book.add_author("Prothom Alo")

    spine = ['nav']

    for index, img_file in enumerate(captured_images, start=1):
        with open(img_file, 'rb') as f:
            raw_img = f.read()

        # Add image asset
        epub_img = epub.EpubItem(
            uid=f"page_img_{index}",
            file_name=f"images/page_{index}.jpg",
            media_type="image/jpeg",
            content=raw_img
        )
        book.add_item(epub_img)

        # Build full-bleed fixed viewport page
        html_content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>পাতা {index}</title>
    <meta name="viewport" content="width=1920, height=2880"/>
    <style>
        @page {{ margin: 0; padding: 0; }}
        html, body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            background-color: #111111;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        img {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            display: block;
        }}
    </style>
</head>
<body>
    <img src="images/page_{index}.jpg" alt="পৃষ্ঠা {index}" />
</body>
</html>"""

        epub_page = epub.EpubHtml(
            title=f"পৃষ্ঠা {index}",
            file_name=f"page_{index}.xhtml",
            lang="bn"
        )
        epub_page.content = html_content
        book.add_item(epub_page)
        spine.append(epub_page)

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_epub, book, {})
    print(f"[✓] EPUB generation successful: {output_epub}")

if __name__ == "__main__":
    extract_epaper_pages()
