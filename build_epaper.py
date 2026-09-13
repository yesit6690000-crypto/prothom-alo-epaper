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

        scraped_stories = []

        # Intercept JSON article payloads directly from backend network traffic
        async def handle_response(response):
            try:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type and response.status == 200:
                    if any(k in response.url.lower() for k in ["article", "story", "getpage", "details"]):
                        data = await response.json()
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            title = item.get("Headline") or item.get("title") or item.get("Title") or ""
                            content = item.get("Body") or item.get("content") or item.get("Description") or ""
                            img = item.get("ImageUrl") or item.get("image") or None
                            if title or content:
                                scraped_stories.append({
                                    "title": str(title).strip(),
                                    "image_url": img,
                                    "paragraphs": [p.strip() for p in str(content).split("\n") if len(p.strip()) > 10]
                                })
            except Exception:
                pass

        page.on("response", handle_response)

        print("[*] Loading Prothom Alo ePaper portal...")
        await page.goto("https://epaper.prothomalo.com/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(6000)

        # Fallback: Scrape rendered article nodes directly from DOM
        if not scraped_stories:
            print("[*] Parsing story blocks from browser DOM...")
            dom_stories = await page.evaluate('''() => {
                const results = [];
                const blocks = document.querySelectorAll('article, .story-box, .article-content, .page-story, map area, div[data-article-id]');
                
                blocks.forEach(b => {
                    const title = b.getAttribute('title') || b.getAttribute('alt') || b.querySelector('h1, h2, h3, .title, .headline')?.innerText.trim() || '';
                    const img = b.querySelector('img')?.src || null;
                    const paras = Array.from(b.querySelectorAll('p, .desc')).map(p => p.innerText.trim()).filter(t => t.length > 15);
                    
                    if (title.length > 3 || paras.length > 0) {
                        results.push({
                            title: title,
                            image_url: img,
                            paragraphs: paras
                        });
                    }
                });
                return results;
            }''')

            for s in dom_stories:
                if not any(existing['title'] == s['title'] for existing in scraped_stories if s['title']):
                    scraped_stories.append(s)

        await browser.close()

    print(f"[*] Total reflowable articles retrieved: {len(scraped_stories)}")

    if not scraped_stories:
        raise Exception("Could not extract article text. Please verify subscription login cookies.")

    # Build Kindle Reflowable EPUB
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
        if story.get("image_url") and str(story["image_url"]).startswith("http"):
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

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] Reflowable EPUB created: {output_filename}")

if __name__ == "__main__":
    asyncio.run(main())
