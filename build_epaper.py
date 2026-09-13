import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from ebooklib import epub

RAW_COOKIE_JSON = os.getenv("EPAPER_COOKIE_JSON", "").strip()

def get_authenticated_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": "https://epaper.prothomalo.com/"
    })

    if not RAW_COOKIE_JSON:
        raise Exception("EPAPER_COOKIE_JSON secret is missing from GitHub Secrets.")

    try:
        cookies_data = json.loads(RAW_COOKIE_JSON)
        for cookie in cookies_data:
            name = cookie.get("name")
            value = cookie.get("value")
            domain = cookie.get("domain", ".prothomalo.com")
            path = cookie.get("path", "/")
            if name and value:
                session.cookies.set(name, value, domain=domain, path=path)
        print(f"[+] Successfully loaded {len(cookies_data)} cookies into session.")
    except Exception as e:
        raise Exception(f"Failed to parse JSON cookie string: {e}")

    return session

def fetch_broadsheet_images(session):
    base_url = "https://epaper.prothomalo.com/"
    print(f"[*] Accessing main portal: {base_url}")
    res = session.get(base_url, timeout=15)
    
    if res.status_code != 200:
        print(f"[-] Failed to access home page. Status: {res.status_code}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    img_urls = []

    # Extract page scan URLs from HTML tags
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        if src and any(k in src.lower() for k in ["page", "epaper", "edition", "uploads"]):
            if not any(ign in src.lower() for ign in ["logo", "icon", "banner", "ad"]):
                if not src.startswith("http"):
                    src = "https://epaper.prothomalo.com" + ("/" if not src.startswith("/") else "") + src
                if src not in img_urls:
                    img_urls.append(src)

    # Fallback regex extraction from embedded page scripts
    if not img_urls:
        matches = re.findall(r'https?://[^\s"\']+\.(?:jpg|jpeg|png|webp)', res.text, re.IGNORECASE)
        for url in matches:
            if any(k in url.lower() for k in ["page", "epaper", "uploads"]) and url not in img_urls:
                img_urls.append(url)

    return img_urls

def run():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_epaper_{today_str}.epub"

    session = get_authenticated_session()
    image_urls = fetch_broadsheet_images(session)

    print(f"[*] Discovered {len(image_urls)} broadsheet page scans.")

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

    for i, img_url in enumerate(image_urls, start=1):
        try:
            res = session.get(img_url, timeout=15)
            if res.status_code == 200 and len(res.content) > 10000:
                img_item = epub.EpubItem(
                    uid=f"page_img_{i}",
                    file_name=f"images/page_{i}.jpg",
                    media_type="image/jpeg",
                    content=res.content
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
                print(f"[+] Downloaded Page {i}")
        except Exception as e:
            print(f"[-] Error downloading page {i}: {e}")

    if not chapters:
        raise Exception("No valid ePaper pages could be extracted. Refresh your browser session cookies.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] ePaper EPUB generated successfully: {output_filename}")

if __name__ == "__main__":
    run()
