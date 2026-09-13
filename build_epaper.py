import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from ebooklib import epub

USERNAME = os.getenv("EPAPER_USER", "")
PASSWORD = os.getenv("EPAPER_PASS", "")

def get_authenticated_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://epaper.prothomalo.com/"
    })

    login_url = "https://epaper.prothomalo.com/Account/Login"
    login_data = {
        "UserName": USERNAME,
        "Password": PASSWORD,
        "RememberMe": "true"
    }

    print("[*] Logging in to Prothom Alo ePaper from GitHub Runner...")
    res = session.post(login_url, data=login_data, timeout=15)
    
    if ".ASPXAUTH" not in session.cookies.get_dict():
        raise Exception("Login failed. Check EPAPER_USER and EPAPER_PASS secrets.")
    
    print("[+] Login successful! Fresh session token acquired.")
    return session

def run():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_epaper_{today_str}.epub"

    session = get_authenticated_session()
    
    book = epub.EpubBook()
    book.set_identifier(f"prothom-alo-epaper-{today_str}")
    book.set_title(f"প্রথম আলো ইপেপার - {today_str}")
    book.set_language("bn")
    book.add_author("দৈনিক প্রথম আলো")

    style = 'body { background-color: #000; margin: 0; padding: 0; text-align: center; } img { max-width: 100%; height: auto; }'
    css_item = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=style)
    book.add_item(css_item)

    chapters = []
    spine = ['nav']

    for page_num in range(1, 17):
        img_url = f"https://epaper.prothomalo.com/Home/GetPageImage?date={today_str}&page={page_num}&edition=dhaka"
        try:
            res = session.get(img_url, timeout=15)
            if res.status_code == 200 and len(res.content) > 15000:
                img_item = epub.EpubItem(
                    uid=f"page_img_{page_num}",
                    file_name=f"images/page_{page_num}.jpg",
                    media_type="image/jpeg",
                    content=res.content
                )
                book.add_item(img_item)

                chapter = epub.EpubHtml(title=f"পাতা {page_num}", file_name=f"page_{page_num}.xhtml", lang="bn")
                chapter.content = f'<html><head><link rel="stylesheet" href="style.css"/></head><body><div><img src="images/page_{page_num}.jpg"/></div></body></html>'
                chapter.add_item(css_item)
                book.add_item(chapter)
                chapters.append(chapter)
                spine.append(chapter)
                print(f"[+] Downloaded Page {page_num}")
            else:
                if page_num > 2:
                    break
        except Exception as e:
            print(f"[-] Error downloading page {page_num}: {e}")

    if not chapters:
        raise Exception("Could not download pages after authentication.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] ePaper EPUB generated: {output_filename}")

if __name__ == "__main__":
    run()
