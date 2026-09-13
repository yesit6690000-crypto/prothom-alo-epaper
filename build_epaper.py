import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from ebooklib import epub

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://epaper.prothomalo.com/"
}

def generate_print_edition_epub():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_print_edition_{today_str}.epub"
    
    print(f"[*] Accessing Prothom Alo Print Edition for {today_str}...")
    base_url = "https://epaper.prothomalo.com/"
    
    resp = requests.get(base_url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        raise Exception(f"Failed to load ePaper portal (HTTP {resp.status_code})")

    soup = BeautifulSoup(resp.text, 'lxml')

    # Initialize EPUB
    book = epub.EpubBook()
    book.set_identifier(f"prothom-alo-print-edition-{today_str}")
    book.set_title(f"প্রথম আলো ছাপা সংস্করণ - {today_str}")
    book.set_language("bn")
    book.add_author("দৈনিক প্রথম আলো")

    style = '''
    @namespace epub "http://www.idpf.org/2007/ops";
    body {
        font-family: SolaimanLipi, Kalpurush, sans-serif;
        font-size: 1.15em;
        line-height: 1.7;
        margin: 5%;
    }
    h1 {
        font-size: 1.5em;
        line-height: 1.3;
        color: #111;
        border-bottom: 2px solid #ccc;
        padding-bottom: 5px;
        margin-bottom: 1em;
    }
    .article-box {
        margin-bottom: 2em;
    }
    .article-title {
        font-size: 1.2em;
        font-weight: bold;
        color: #d32f2f;
        margin-bottom: 0.5em;
    }
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 10px auto;
        border-radius: 4px;
    }
    p {
        margin-bottom: 0.8em;
        text-align: justify;
    }
    '''
    default_css = epub.EpubItem(uid="style_nav", file_name="style/default.css", media_type="text/css", content=style)
    book.add_item(default_css)

    chapters = []
    spine = ['nav']
    img_counter = 1

    # Find edition page links or category editions from the portal
    edition_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'edition' in href or 'page' in href or 'detail' in href:
            full_url = href if href.startswith("http") else f"https://epaper.prothomalo.com{href}"
            if full_url not in edition_links:
                edition_links.append(full_url)

    print(f"[*] Discovered {len(edition_links)} print sections/pages.")

    # Fallback to general print items if direct links are restricted
    if not edition_links:
        edition_links = [base_url]

    added_articles_count = 0

    for p_idx, link in enumerate(edition_links[:12], start=1):
        try:
            page_resp = requests.get(link, headers=HEADERS, timeout=15)
            if page_resp.status_code != 200:
                continue
            
            page_soup = BeautifulSoup(page_resp.text, 'lxml')
            
            # Extract articles mapped on this print page
            story_blocks = page_soup.find_all(['div', 'article'], class_=lambda c: c and ('story' in c or 'article' in c or 'card' in c))
            
            if not story_blocks:
                # Generic fallback to links matching news patterns
                story_blocks = page_soup.find_all('a', href=True)

            page_content_html = f"<h1>পৃষ্ঠা {p_idx}</h1>"
            page_has_content = False

            for block in story_blocks[:15]:
                title_elem = block.find(['h2', 'h3', 'h4', 'span', 'a'])
                if not title_elem:
                    continue
                title_text = title_elem.get_text().strip()
                if len(title_text) < 10:
                    continue

                # Find associated image inside the print block
                img_tag = block.find('img', src=True)
                img_html = ""
                if img_tag:
                    img_url = img_tag['src']
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    if img_url.startswith("http"):
                        try:
                            img_data = requests.get(img_url, headers=HEADERS, timeout=5).content
                            img_item = epub.EpubItem(
                                uid=f"img_{img_counter}",
                                file_name=f"images/img_{img_counter}.jpg",
                                media_type="image/jpeg",
                                content=img_data
                            )
                            book.add_item(img_item)
                            img_html = f'<p><img src="images/img_{img_counter}.jpg" alt="Print Image"/></p>'
                            img_counter += 1
                        except Exception:
                            pass

                page_content_html += f"""
                <div class="article-box">
                    <div class="article-title">{title_text}</div>
                    {img_html}
                </div>
                """
                page_has_content = True
                added_articles_count += 1

            if page_has_content:
                chapter = epub.EpubHtml(title=f"পাতা {p_idx}", file_name=f"print_page_{p_idx}.xhtml", lang="bn")
                chapter.content = f"<html><head><link rel='stylesheet' href='style/default.css'/></head><body>{page_content_html}</body></html>"
                chapter.add_item(default_css)
                book.add_item(chapter)
                chapters.append(chapter)
                spine.append(chapter)
                print(f"[+] Compiled Print Page {p_idx}")

        except Exception as e:
            print(f"[-] Error on page link {link}: {e}")

    if not chapters:
        raise Exception("Could not map print pages.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] Print Edition EPUB generated: {output_filename}")

if __name__ == "__main__":
    generate_print_edition_epub()
