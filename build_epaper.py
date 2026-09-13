import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from ebooklib import epub

USERNAME = os.getenv("EPAPER_USER", "").strip()
PASSWORD = os.getenv("EPAPER_PASS", "").strip()

def get_authenticated_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
        "Referer": "https://epaper.prothomalo.com/Account/Login"
    })

    login_url = "https://epaper.prothomalo.com/Account/Login"

    print("[*] Requesting login page for verification token...")
    get_res = session.get(login_url, timeout=15)
    
    if get_res.status_code == 403 or "cloudflare" in get_res.text.lower():
        print("[!] GitHub runner IP is being blocked by Cloudflare security.")
        
    soup = BeautifulSoup(get_res.text, "html.parser")
    token_tag = soup.find("input", {"name": "__RequestVerificationToken"})
    token_val = token_tag.get("value", "") if token_tag else ""

    login_data = {
        "__RequestVerificationToken": token_val,
        "UserName": USERNAME,
        "Password": PASSWORD,
        "RememberMe": "true"
    }

    print(f"[*] Submitting login for account target...")
    res = session.post(login_url, data=login_data, timeout=15)

    print(f"[*] Status Code: {res.status_code}")
    print(f"[*] Final URL: {res.url}")

    cookies = session.cookies.get_dict()
    if ".ASPXAUTH" not in cookies and "Logout" not in res.text and "logout" not in res.text.lower():
        print(f"[-] Server response snippet: {res.text[:250]}")
        raise Exception("Login failed. Check logs above for response details.")

    print("[+] Login successful! Active session established.")
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
            res = session.get(img_url, timeout=15)
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
                print(f"[+] Downloaded Page {page_num} ({len(res.content)} bytes)")
            elif page_num > 2:
                break
        except Exception as e:
            print(f"[-] Error downloading page {page_num}: {e}")
            if page_num > 2:
                break

    if not chapters:
        raise Exception("Could not download pages. Verify subscription status or account credentials.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] ePaper EPUB generated successfully: {output_filename}")

if __name__ == "__main__":
    run()
