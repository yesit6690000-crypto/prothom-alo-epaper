import os
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from ebooklib import epub

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

def fetch_latest_articles():
    # Use Prothom Alo's internal API to query today's articles cleanly
    now = datetime.now()
    start_time = int((now - timedelta(days=1)).timestamp() * 1000)
    end_time = int(now.timestamp() * 1000)

    api_url = f"https://www.prothomalo.com/api/v1/advanced-search?fields=headline,tags,published-at,cards,slug,story-elements&limit=40&published-after={start_time}&published-before={end_time}&sort=latest-published"
    
    print(f"[*] Fetching articles via Prothom Alo API...")
    resp = requests.get(api_url, headers=HEADERS, timeout=20)
    
    if resp.status_code != 200:
        # Fallback query without tight date bounds if early morning
        api_url = "https://www.prothomalo.com/api/v1/advanced-search?fields=headline,tags,published-at,cards,slug,story-elements&limit=35&sort=latest-published"
        resp = requests.get(api_url, headers=HEADERS, timeout=20)

    data = resp.json()
    items = data.get("items", [])
    print(f"[*] Retrieved {len(items)} articles.")
    return items

def generate_epub():
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_filename = f"prothom_alo_print_{today_str}.epub"

    items = fetch_latest_articles()
    if not items:
        raise Exception("API returned 0 items. Could not build EPUB.")

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

    for idx, item in enumerate(items, start=1):
        headline = item.get("headline", "").strip()
        slug = item.get("slug", "")
        if not headline or not slug:
            continue

        # Extract content cards/paragraphs directly from API payload
        paragraphs = []
        cards = item.get("cards", [])
        for card in cards:
            story_elements = card.get("story-elements", [])
            for elem in story_elements:
                if elem.get("type") == "text":
                    text_html = elem.get("text", "")
                    # Extract plain text from element HTML snippet
                    soup_p = BeautifulSoup(text_html, 'html.parser')
                    p_text = soup_p.get_text().strip()
                    if len(p_text) > 15:
                        paragraphs.append(f"<p>{p_text}</p>")

        if not paragraphs:
            continue

        # Extract lead hero image URL from API metadata
        img_html = ""
        hero_image_s3 = item.get("hero-image-s3-key")
        if hero_image_s3:
            img_url = f"https://images.prothomalo.com/{hero_image_s3}?w=800&auto=format%2Ccompress"
            try:
                img_data = requests.get(img_url, headers=HEADERS, timeout=8).content
                img_item = epub.EpubItem(
                    uid=f"img_{img_counter}",
                    file_name=f"images/img_{img_counter}.jpg",
                    media_type="image/jpeg",
                    content=img_data
                )
                book.add_item(img_item)
                img_html = f'<p><img src="images/img_{img_counter}.jpg" alt="Photo"/></p>'
                img_counter += 1
            except Exception:
                pass

        html_content = f"""
        <html>
        <head>
            <title>{headline}</title>
            <link rel="stylesheet" href="style/default.css" type="text/css"/>
        </head>
        <body>
            <h1>{headline}</h1>
            {img_html}
            {''.join(paragraphs)}
        </body>
        </html>
        """

        chapter = epub.EpubHtml(title=headline, file_name=f"article_{idx}.xhtml", lang="bn")
        chapter.content = html_content
        chapter.add_item(default_css)
        book.add_item(chapter)
        chapters.append(chapter)
        spine.append(chapter)
        print(f"[+] Added article {idx}: {headline[:40]}...")

    if not chapters:
        raise Exception("Failed to compile any valid article chapters.")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(output_filename, book, {})
    print(f"[✓] EPUB successfully generated: {output_filename}")

if __name__ == "__main__":
    generate_epub()
