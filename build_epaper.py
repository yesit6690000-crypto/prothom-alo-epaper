import os
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
from ebooklib import epub

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "bn,en-US;q=0.7,en;q=0.3"
}

FEEDS = [
    ("বাংলাদেশ", "https://www.prothomalo.com/feed/bangladesh"),
    ("আন্তর্জাতিক", "https://www.prothomalo.com/feed/world"),
    ("বাণিজ্য", "https://www.prothomalo.com/feed/business"),
    ("মতামত", "https://www.prothomalo.com/feed/opinion"),
    ("খেলা", "https://www.prothomalo.com/feed/sports"),
    ("বিনোদন", "https://www.prothomalo.com/feed/entertainment"),
]

def fetch_feed_urls():
    articles = []
    for section_name, feed_url in FEEDS:
        try:
            resp = requests.get(feed_url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    if title_elem is not None and link_elem is not None:
                        articles.append({
                            "section": section_name,
                            "title": title_elem.text.strip(),
                            "url": link_elem.text.strip()
                        })
        except Exception as e:
            print(f"[-] Could not read feed {section_name}: {e}")
    return articles

def generate_epub():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_print_{today_str}.epub"
    print(f"[*] Fetching Prothom Alo news for {today_str}...")

    all_items = fetch_feed_urls()
    
    # Deduplicate by URL
    seen_urls = set()
    unique_articles = []
    for item in all_items:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            unique_articles.append(item)

    print(f"[*] Found {len(unique_articles)} articles across all categories.")

    book = epub.EpubBook()
    book.set_identifier(f"prothom-alo-{today_str}")
    book.set_title(f"প্রথম আলো - {today_str}")
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
        font-size: 1.6em;
        line-height: 1.3;
        margin-bottom: 0.3em;
        color: #111;
    }
    .meta {
        color: #666;
        font-size: 0.9em;
        margin-bottom: 1.5em;
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

    # Extract up to 30 top articles
    for idx, art in enumerate(unique_articles[:30], start=1):
        try:
            art_resp = requests.get(art["url"], headers=HEADERS, timeout=12)
            if art_resp.status_code != 200:
                continue

            soup = BeautifulSoup(art_resp.text, 'lxml')

            # Extract body content from story container
            story_div = soup.find('div', class_=lambda c: c and 'story-element' in c) or soup.find('article') or soup
            paragraphs = []
            for p in story_div.find_all('p'):
                text = p.get_text().strip()
                if len(text) > 25 and "বিজ্ঞাপন" not in text:
                    paragraphs.append(f"<p>{text}</p>")

            if not paragraphs:
                continue

            # Extract lead image
            img_html = ""
            img_tag = soup.find('img', src=lambda s: s and ('media' in s or 'images' in s))
            if img_tag and img_tag.get('src'):
                img_url = img_tag['src']
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                try:
                    img_data = requests.get(img_url, headers=HEADERS, timeout=8).content
                    img_item = epub.EpubItem(
                        uid=f"img_{img_counter}",
                        file_name=f"images/img_{img_counter}.jpg",
                        media_type="image/jpeg",
                        content=img_data
                    )
                    book.add_item(img_item)
                    img_html = f'<p><img src="images/img_{img_counter}.jpg" alt="Image"/></p>'
                    img_counter += 1
                except Exception:
                    pass

            html_content = f"""
            <html>
            <head>
                <title>{art['title']}</title>
                <link rel="stylesheet" href="style/default.css" type="text/css"/>
            </head>
            <body>
                <div class="meta">বিভাগ: {art['section']}</div>
                <h1>{art['title']}</h1>
                {img_html}
                {''.join(paragraphs)}
            </body>
            </html>
            """

            chapter = epub.EpubHtml(title=art['title'], file_name=f"article_{idx}.xhtml", lang="bn")
            chapter.content = html_content
            chapter.add_item(default_css)
            book.add_item(chapter)
            chapters.append(chapter)
            spine.append(chapter)
            print(f"[+] Added ({art['section']}): {art['title'][:40]}...")

        except Exception as e:
            print(f"[-] Error parsing {art['url']}: {e}")

    if not chapters:
        raise Exception("Could not collect any articles.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] EPUB ready: {output_filename}")

if __name__ == "__main__":
    generate_epub()
