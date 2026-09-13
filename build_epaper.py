import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from ebooklib import epub

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def run():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_{today_str}.epub"
    base_url = "https://www.prothomalo.com"
    
    print(f"[*] Fetching daily Prothom Alo content for {today_str}...")
    resp = requests.get(base_url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, 'html.parser')

    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(cat in href for cat in ['/bangladesh/', '/world/', '/business/', '/sports/', '/entertainment/', '/opinion/']):
            full_url = href if href.startswith("http") else f"{base_url}{href}"
            if full_url not in links:
                links.append(full_url)

    print(f"[*] Found {len(links)} stories. Packaging into EPUB...")

    book = epub.EpubBook()
    book.set_identifier(f"prothom-alo-{today_str}")
    book.set_title(f"প্রথম আলো - {today_str}")
    book.set_language("bn")
    book.add_author("দৈনিক প্রথম আলো")

    style = '''
    body { font-family: SolaimanLipi, Kalpurush, sans-serif; font-size: 1.15em; line-height: 1.7; margin: 5%; }
    h1 { font-size: 1.5em; line-height: 1.3; color: #111; margin-bottom: 0.5em; }
    img { max-width: 100%; height: auto; display: block; margin: 15px auto; border-radius: 4px; }
    p { margin-bottom: 1em; text-align: justify; }
    '''
    css_item = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=style)
    book.add_item(css_item)

    chapters = []
    spine = ['nav']
    img_counter = 1

    for idx, url in enumerate(links[:30], start=1):
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code != 200:
                continue
            
            art_soup = BeautifulSoup(res.text, 'html.parser')
            h1 = art_soup.find('h1')
            title = h1.get_text().strip() if h1 else f"Story {idx}"

            paragraphs = []
            for p in art_soup.find_all('p'):
                text = p.get_text().strip()
                if len(text) > 25 and "বিজ্ঞাপন" not in text:
                    paragraphs.append(f"<p>{text}</p>")

            if not paragraphs:
                continue

            img_html = ""
            img_tag = art_soup.find('img', src=True)
            if img_tag:
                src = img_tag['src']
                if src.startswith("//"): 
                    src = "https:" + src
                if src.startswith("http") and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    try:
                        img_data = requests.get(src, headers=HEADERS, timeout=6).content
                        img_item = epub.EpubItem(
                            uid=f"img_{img_counter}",
                            file_name=f"images/img_{img_counter}.jpg",
                            media_type="image/jpeg",
                            content=img_data
                        )
                        book.add_item(img_item)
                        img_html = f'<p><img src="images/img_{img_counter}.jpg" alt=""/></p>'
                        img_counter += 1
                    except Exception:
                        pass

            html_content = f"""
            <html>
            <head><title>{title}</title><link rel="stylesheet" href="style.css" type="text/css"/></head>
            <body>
                <h1>{title}</h1>
                {img_html}
                {''.join(paragraphs)}
            </body>
            </html>
            """

            ch = epub.EpubHtml(title=title, file_name=f"article_{idx}.xhtml", lang="bn")
            ch.content = html_content
            ch.add_item(css_item)
            book.add_item(ch)
            chapters.append(ch)
            spine.append(ch)
        except Exception:
            continue

    if not chapters:
        raise Exception("No content compiled.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] EPUB generated: {output_filename}")

if __name__ == "__main__":
    run()
