import os
import json
import asyncio
import requests
from datetime import datetime
from playwright.async_api import async_playwright
from ebooklib import epub

RAW_COOKIE_JSON = os.getenv("EPAPER_COOKIE_JSON", "").strip()

async def main():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_epaper_{today_str}.epub"

    if not RAW_COOKIE_JSON:
        raise Exception("EPAPER_COOKIE_JSON secret is missing from GitHub Secrets.")

    cookies = json.loads(RAW_COOKIE_JSON)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
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

        print("[*] Navigating to Prothom Alo ePaper...")
        # Use domcontentloaded to avoid long-polling background timeouts
        await page.goto("https://epaper.prothomalo.com/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        # Scrape clickable story blocks or map links
        scraped_stories = []
        areas = await page.query_selector_all('map area, div.article-box, a.page-link, [data-article-id]')
        print(f"[*] Found {len(areas)} potential article elements.")

        for idx, area in enumerate(areas[:20]):
            try:
                await area.click(force=True, timeout=3000)
                await page.wait_for_timeout(1000)

                story = await page.evaluate('''() => {
                    const modal = document.querySelector('.modal-content, .article-detail-popup, #articleModal, .story-details, body');
                    if (!modal) return null;

                    const titleEl = modal.querySelector('h1, h2, .headline, .title');
                    const title = titleEl ? titleEl.innerText.trim() : '';

                    const imgs = Array.from(modal.querySelectorAll('img'))
                        .map(i => i.src)
                        .filter(src => src && !src.includes('logo') && !src.includes('icon'));

                    const paragraphs = Array.from(modal.querySelectorAll('p, .content, .description'))
                        .map(p => p.innerText.trim())
                        .filter(t => t.length > 15);

                    return {
                        title: title,
                        image_url: imgs.length > 0 ? imgs[0] : null,
                        paragraphs: paragraphs
                    };
                }''')

                if story and (story['title'] or story['paragraphs']):
                    scraped_stories.append(story)
                    print(f"[+] Scraped: {story['title'][:40]}...")

                # Close modal view if open
                close_btn = await page.query_selector('.close, .btn-close, .modal-close')
                if close_btn:
                    await close_btn.click(timeout=1000)
            except Exception:
                continue

        await browser.close()

    # Package into Kindle Reflowable EPUB
    book = epub.EpubBook()
    book.set_identifier(f"prothom-alo-epaper-text-{today_str}")
    book.set_title(f"প্রথম আলো - {today_str}")
    book.set_language("bn")
    book.add_author("দৈনিক প্রথম আলো")

    style = '''
    @namespace epub "http://www.idpf.org/2007/ops";
    body { font-family: "Kalpurush", "SolaimanLipi", sans-serif; padding: 4%; line-height: 1.6; }
    h1 { font-size: 1.5em; color: #111; margin-bottom: 0.5em; line-height: 1.3; }
    img { max-width: 100%; height: auto; display: block; margin: 1em auto; }
    p { font-size: 1.1em; text-align: justify; text-indent: 1em; margin-bottom: 0.8em; }
    '''
    css_item = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=style)
    book.add_item(css_item)

    chapters = []
    spine = ['nav']
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    for i, story in enumerate(scraped_stories, start=1):
        img_html = ""
        if story.get("image_url"):
            try:
                res = session.get(story["image_url"], timeout=10)
                if res.status_code == 200:
                    img_name = f"img_{i}.jpg"
                    img_item = epub.EpubItem(
                        uid=f"img_{i}",
                        file_name=f"images/{img_name}",
                        media_type="image/jpeg",
                        content=res.content
                    )
                    book.add_item(img_item)
                    img_html = f'<img src="images/{img_name}" alt="Article Image"/>'
            except Exception:
                pass

        paras_html = "".join([f"<p>{p}</p>" for p in story["paragraphs"]])
        title_text = story["title"] or f"সংবাদ {i}"

        chapter = epub.EpubHtml(
            title=title_text,
            file_name=f"article_{i}.xhtml",
            lang="bn"
        )
        chapter.content = f"""
        <html>
        <head><title>{title_text}</title><link rel="stylesheet" href="style.css" type="text/css"/></head>
        <body>
            <h1>{title_text}</h1>
            {img_html}
            {paras_html}
        </body>
        </html>
        """
        chapter.add_item(css_item)
        book.add_item(chapter)
        chapters.append(chapter)
        spine.append(chapter)

    if not chapters:
        raise Exception("Could not extract article text from portal.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] Reflowable text+image EPUB generated: {output_filename}")

if __name__ == "__main__":
    asyncio.run(main())
