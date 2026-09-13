import os
import json
import requests
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

def download_page_image(session, today_str, page_num):
    urls_to_try = [
        f"https://epaper.prothomalo.com/Home/GetPageImage?date={today_str}&page={page_num}&edition=dhaka",
        f"https://epaper.prothomalo.com/Home/GetPageImage?date={today_str}&page={page_num}",
        f"https://epaper.prothomalo.com/Home/PageImage?date={today_str}&page={page_num}"
    ]

    for url in urls_to_try:
        try:
            res = session.get(url, timeout=15)
            content_type = res.headers.get("Content-Type", "")
            print(f"[*] Page {page_num} attempt -> Status: {res.status_code} | Size: {len(res.content)} bytes | Type: {content_type}")
            
            if res.status_code == 200 and "image" in content_type.lower() and len(res.content) > 10000:
                return res.content
            elif "text/html" in content_type.lower() and len(res.content) < 5000:
                print(f"[-] HTML snippet: {res.text[:150].strip()}")
        except Exception as e:
            print(f"[-] Request error for Page {page_num}: {e}")

    return None

def run():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_epaper_{today_str}.epub"

    session = get_authenticated_session()

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

    for page_num in range(1, 17):
        img_data = download_page_image(session, today_str, page_num)
        if img_data:
            img_item = epub.EpubItem(
                uid=f"page_img_{page_num}",
                file_name=f"images/page_{page_num}.jpg",
                media_type="image/jpeg",
                content=img_data
            )
            book.add_item(img_item)

            chapter = epub.EpubHtml(
                title=f"পাতা {page_num}",
                file_name=f"page_{page_num}.xhtml",
                lang="bn"
            )
            chapter.content = f"""
            <html>
            <head><title>পাতা {page_num}</title><link rel="stylesheet" href="style.css" type="text/css"/></head>
            <body>
                <div class="page"><img src="images/page_{page_num}.jpg" alt="Page {page_num}"/></div>
            </body>
            </html>
            """
            chapter.add_item(css_item)
            book.add_item(chapter)
            chapters.append(chapter)
            spine.append(chapter)
            print(f"[+] Successfully attached Page {page_num}")
        elif page_num > 2:
            print(f"[*] Stopping scan at page {page_num} (no further content).")
            break

    if not chapters:
        raise Exception("Could not download pages. Your logged-in web session has likely expired. Re-export cookies from your browser.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] ePaper EPUB generated successfully: {output_filename}")

if __name__ == "__main__":
    run()
