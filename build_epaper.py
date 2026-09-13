import os
import requests
from datetime import datetime
from ebooklib import epub

# Retrieve cookie and sanitize invisible/non-ASCII characters (\u2060)
raw_cookie = os.getenv("EPAPER_COOKIE", "")
COOKIE = "".join(char for char in raw_cookie if ord(char) < 128).strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
    "Referer": "https://epaper.prothomalo.com/",
    "Cookie": COOKIE
}

def run():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_epaper_{today_str}.epub"
    
    print(f"[*] Starting ePaper fetch for date: {today_str}")
    if not COOKIE:
        print("[!] WARNING: EPAPER_COOKIE environment variable is empty!")

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
        img_url = f"https://epaper.prothomalo.com/Home/GetPageImage?date={today_str}&page={page_num}&edition=dhaka"
        
        try:
            res = requests.get(img_url, headers=HEADERS, timeout=15, allow_redirects=False)
            content_type = res.headers.get("Content-Type", "")
            
            if res.status_code == 200 and ("image" in content_type or len(res.content) > 15000):
                img_item = epub.EpubItem(
                    uid=f"page_img_{page_num}",
                    file_name=f"images/page_{page_num}.jpg",
                    media_type="image/jpeg",
                    content=res.content
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
                print(f"[+] Downloaded Page {page_num} ({len(res.content)} bytes)")
            else:
                print(f"[-] Page {page_num} response: HTTP {res.status_code} | Size: {len(res.content)} bytes")
                if page_num > 2:
                    break
        except Exception as e:
            print(f"[-] Request error on page {page_num}: {e}")
            if page_num > 2:
                break

    if not chapters:
        raise Exception("Failed to fetch ePaper pages. Verify that your secret cookie is still valid.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] ePaper EPUB generated successfully: {output_filename}")

if __name__ == "__main__":
    run()
