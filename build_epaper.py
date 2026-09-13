import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from ebooklib import epub

RAW_COOKIE_JSON = os.getenv("EPAPER_COOKIE_JSON", "").strip()

def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://epaper.prothomalo.com/"
    })

    if RAW_COOKIE_JSON:
        try:
            cookies = json.loads(RAW_COOKIE_JSON)
            for c in cookies:
                name = c.get("name")
                value = c.get("value")
                domain = c.get("domain", ".prothomalo.com")
                path = c.get("path", "/")
                if name and value:
                    session.cookies.set(name, value, domain=domain, path=path)
            print(f"[+] Loaded {len(cookies)} cookies into session.")
        except Exception as e:
            print(f"[-] Cookie warning: {e}")

    return session

def fetch_stories(session):
    stories = []
    
    # 1. Direct ePaper API / RSS Feed extraction
    feed_urls = [
        "https://www.prothomalo.com/feed",
        "https://epaper.prothomalo.com/rss/edition"
    ]

    for feed in feed_urls:
        try:
            res = session.get(feed, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "xml")
                items = soup.find_all("item")
                for item in items:
                    title = item.find("title")
                    desc = item.find("description")
                    enc = item.find("enclosure")
                    
                    img_url = enc.get("url") if enc and enc.has_attr("url") else None
                    title_text = title.get_text(strip=True) if title else ""
                    
                    paras = []
                    if desc:
                        body_soup = BeautifulSoup(desc.get_text(), "html.parser")
                        paras = [p.get_text(strip=True) for p in body_soup.find_all(["p", "div"]) if len(p.get_text(strip=True)) > 15]
                        if not paras and body_soup.get_text(strip=True):
                            paras = [body_soup.get_text(strip=True)]

                    if title_text and paras:
                        stories.append({
                            "title": title_text,
                            "image_url": img_url,
                            "paragraphs": paras
                        })
                if stories:
                    break
        except Exception as e:
            print(f"[-] Feed scan error: {e}")

    # 2. Web Portal Fallback Scraper
    if not stories:
        print("[*] Fetching frontpage articles directly from website portal...")
        try:
            res = session.get("https://www.prothomalo.com/", timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                links = soup.find_all("a", href=True)
                article_urls = list(set([l["href"] for l in links if "/bangladesh/" in l["href"] or "/international/" in l["href"] or "/sports/" in l["href"]]))

                for url in article_urls[:30]:
                    if not url.startswith("http"):
                        url = "https://www.prothomalo.com" + url
                    try:
                        art_res = session.get(url, timeout=8)
                        if art_res.status_code == 200:
                            art_soup = BeautifulSoup(art_res.text, "html.parser")
                            h1 = art_soup.find("h1")
                            p_tags = [p.get_text(strip=True) for p in art_soup.find_all("p") if len(p.get_text(strip=True)) > 20]
                            img = art_soup.find("img")
                            img_src = img.get("src") if img else None

                            if h1 and p_tags:
                                stories.append({
                                    "title": h1.get_text(strip=True),
                                    "image_url": img_src,
                                    "paragraphs": p_tags
                                })
                    except Exception:
                        continue
        except Exception as e:
            print(f"[-] Portal scraper error: {e}")

    return stories

def main():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_epaper_{today_str}.epub"

    session = get_session()
    stories = fetch_stories(session)

    print(f"[*] Total reflowable articles parsed: {len(stories)}")

    if not stories:
        raise Exception("Could not retrieve news articles. Check internet access or cookies.")

    book = epub.EpubBook()
    book.set_identifier(f"prothom-alo-text-{today_str}")
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

    for i, story in enumerate(stories, start=1):
        img_html = ""
        if story.get("image_url") and str(story["image_url"]).startswith("http"):
            try:
                res = session.get(story["image_url"], timeout=8)
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
        title_text = story["title"]

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
    print(f"[✓] Successfully built reflowable EPUB: {output_filename}")

if __name__ == "__main__":
    main()
