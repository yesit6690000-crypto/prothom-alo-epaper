import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from ebooklib import epub

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

def clean_filename(name):
    return "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).rstrip()

def fetch_print_edition():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_print_{today_str}.epub"
    
    print(f"[*] Fetching Prothom Alo Print Edition for {today_str}...")

    # The official Print Edition (ছাপা সংস্করণ) portal
    target_url = "https://www.prothomalo.com/collection/print-edition"
    resp = requests.get(target_url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Failed to access {target_url} (HTTP {resp.status_code})")

    soup = BeautifulSoup(resp.text, 'lxml')

    # Collect article links
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(keyword in href for keyword in ['/bangladesh/', '/international/', '/business/', '/opinion/', '/sports/', '/entertainment/']):
            full_url = href if href.startswith("http") else f"https://www.prothomalo.com{href}"
            if full_url not in links:
                links.append(full_url)

    print(f"[*] Found {len(links)} print edition articles. Extracting...")

    # Initialize Reflowable EPUB
    book = epub.EpubBook()
    book.set_identifier(f"prothom-alo-print-{today_str}")
    book.set_title(f"প্রথম আলো ছাপা সংস্করণ - {today_str}")
    book.set_language("bn")
    book.add_author("Prothom Alo")

    # Global Bengali styling for e-readers
    style = '''
    @namespace epub "http://www.idpf.org/2007/ops";
    body {
        font-family: SolaimanLipi, Kalpurush, sans-serif;
        font-size: 1.15em;
        line-height: 1.7;
        margin: 5%;
    }
    h1 {
        font-size: 1.6em;
        line-height: 1.3;
        margin-bottom: 0.5em;
        color: #111;
    }
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 15px auto;
        border-radius: 4px;
    }
    p {
        margin-bottom: 1em;
        text-align: justify;
    }
    '''
    default_css = epub.EpubItem(uid="style_nav", file_name="style/default.css", media_type="text/css", content=style)
    book.add_item(default_css)

    chapters = []
    spine = ['nav']
    img_counter = 1

    # Extract text and photos from articles (up to 35 top articles)
    for idx, url in enumerate(links[:35], start=1):
        try:
            art_resp = requests.get(url, headers=HEADERS, timeout=15)
            if art_resp.status_code != 200:
                continue
            
            art_soup = BeautifulSoup(art_resp.text, 'lxml')
            
            # Extract title
            title_tag = art_soup.find(['h1', 'title'])
            if not title_tag:
                continue
            title = title_tag.get_text().strip()
            if not title or "Prothom Alo" in title and len(title) < 15:
                continue

            # Extract body paragraphs
            paragraphs = []
            for p in art_soup.find_all('p'):
                text = p.get_text().strip()
                if len(text) > 30 and "বিজ্ঞাপন" not in text:
                    paragraphs.append(f"<p>{text}</p>")

            if not paragraphs:
                continue

            # Extract featured image
            img_html = ""
            img_tag = art_soup.find('img', src=True)
            if img_tag:
                img_url = img_tag['src']
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                if img_url.startswith("http") and any(ext in img_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    try:
                        img_data = requests.get(img_url, headers=HEADERS, timeout=10).content
                        img_item = epub.EpubItem(
                            uid=f"img_{img_counter}",
                            file_name=f"images/img_{img_counter}.jpg",
                            media_type="image/jpeg",
                            content=img_data
                        )
                        book.add_item(img_item)
                        img_html = f'<p><img src="images/img_{img_counter}.jpg" alt="Article image"/></p>'
                        img_counter += 1
                    except Exception:
                        pass

            # Construct chapter page
            content = f"""
            <html>
            <head>
                <title>{title}</title>
                <link rel="stylesheet" href="style/default.css" type="text/css"/>
            </head>
            <body>
                <h1>{title}</h1>
                {img_html}
                {''.join(paragraphs)}
            </body>
            </html>
            """

            chapter = epub.EpubHtml(title=title, file_name=f"article_{idx}.xhtml", lang="bn")
            chapter.content = content
            chapter.add_item(default_css)
            book.add_item(chapter)
            chapters.append(chapter)
            spine.append(chapter)
            print(f"[+] Added article {idx}: {title[:40]}...")

        except Exception as e:
            print(f"[-] Skipped article {url}: {e}")

    if not chapters:
        raise Exception("No article content could be extracted.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] Successfully generated reflowable EPUB: {output_filename}")

if __name__ == "__main__":
    fetch_print_edition()
