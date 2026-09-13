import os
import requests
from datetime import datetime
from ebooklib import epub

# Retrieve secret cookie from GitHub environment
COOKIE = os.getenv("EPAPER_COOKIE", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Cookie": COOKIE,
    "Referer": "https://epaper.prothomalo.com/"
}

def run():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_epaper_{today_str}.epub"
    
    print(f"[*] Downloading ePaper broadsheet scans for {today_str}...")

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

    # Fetch daily print edition pages (up to 16 pages)
    for page_num in range(1, 17):
        img_url = f"https://epaper.prothomalo.com/Home/GetPageImage?date={today_str}&page={page_num}&edition=dhaka"
        
        try:
            res = requests.get(img_url, headers=HEADERS, timeout=15)
            if res.status_code == 200 and len(res.content) > 15000:
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
                print(f"[+] Downloaded Page {page_num}")
            else:
                if page_num > 4:
                    break
        except Exception as e:
            print(f"[-] Error downloading page {page_num}: {e}")

    if not chapters:
        raise Exception("Failed to fetch ePaper pages. Re-check if EPAPER_COOKIE is valid.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] EPUB generated successfully: {output_filename}")

if __name__ == "__main__":
    run()
