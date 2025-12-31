import re
import time

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

from database import SessionLocal, engine, Base
from models import Movie

# Ensure DB tables exist
Base.metadata.create_all(bind=engine)

BASE_URL = "https://www.imdb.com"


def get_full_page_html(url: str, initial_wait: int = 5) -> str:
    """
    Open IMDb with undetected Chrome, scroll to load everything,
    return the final rendered HTML.
    """
    print("[INFO] Starting undetected Chrome...")
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # Do NOT use headless first; some sites behave differently.
    # Once it works, you can experiment with headless.
    # options.add_argument("--headless=new")

    driver = uc.Chrome(options=options)
    try:
        print(f"[INFO] Opening URL: {url}")
        driver.get(url)

        # Wait for JS to load initial content
        print(f"[INFO] Waiting {initial_wait} seconds for page to load...")
        time.sleep(initial_wait)

        # Scroll to bottom to trigger lazy loading (just in case)
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        print("[INFO] Finished scrolling, capturing page source...")
        html = driver.page_source
        return html
    finally:
        driver.quit()
        print("[INFO] Browser closed.")


def scrape_top_movies_with_selenium(limit: int = 250):
    print(f"[INFO] Starting Selenium IMDb Top 250 scrape, limit={limit}")
    url = f"{BASE_URL}/chart/top/"
    html = get_full_page_html(url, initial_wait=7)

    # Save raw HTML once for inspection / debugging
    with open("imdb_selenium_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[INFO] Saved full page HTML to imdb_selenium_page.html")

    soup = BeautifulSoup(html, "html.parser")
    print("[DEBUG] Page title:", soup.title.string if soup.title else "NO TITLE")

    # Try modern ul/li layout
    movie_list_parent = soup.find("ul", class_=re.compile(r"ipc-metadata-list"))
    layout = None
    movie_list = []

    if movie_list_parent:
        movie_list = movie_list_parent.find_all("li", class_="ipc-metadata-list-summary-item")
        layout = "modern-ul-li"
    else:
        # Fallback: classic table layout (older desktop)
        table = soup.find("tbody", class_="lister-list")
        if table:
            movie_list = table.find_all("tr")
            layout = "classic-table"

    print(f"[INFO] Layout detected: {layout}, movies found in HTML: {len(movie_list)}")

    if not movie_list:
        with open("imdb_selenium_debug.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print("[ERROR] No movie list found. Saved imdb_selenium_debug.html")
        return

    db = SessionLocal()
    count = 0

    for movie in movie_list:
        if count >= limit:
            break

        try:
            if layout == "modern-ul-li":
                # ---------- TITLE ----------
                title_element = movie.find("h3", class_="ipc-title__text")
                if not title_element:
                    print("[WARN] Skipping movie with no title element")
                    continue
                full_title = title_element.get_text(strip=True)
                # Titles are like "1. The Shawshank Redemption"
                title = ".".join(full_title.split(".")[1:]).strip() if "." in full_title else full_title

                # ---------- YEAR ----------
                year = None
                year_element = movie.find("span", class_=re.compile(r"cli-title-metadata-item"))
                if year_element:
                    ym = re.search(r"(19|20)\d{2}", year_element.get_text())
                    if ym:
                        year = int(ym.group(0))

                # ---------- RATING ----------
                rating = None
                rating_element = movie.find("span", class_=re.compile(r"ipc-rating-star|AggregateRating|rating"))
                if rating_element:
                    rm = re.search(r"(\d+(?:\.\d+)?)", rating_element.get_text(strip=True))
                    if rm:
                        rating = float(rm.group(1))

            else:  # classic-table
                title_cell = movie.find("td", class_="titleColumn")
                if not title_cell or not title_cell.a:
                    print("[WARN] Skipping table row with no title link")
                    continue
                title = title_cell.a.get_text(strip=True)

                year = None
                year_span = title_cell.find("span", class_="secondaryInfo")
                if year_span:
                    year_text = year_span.get_text(strip=True)
                    year = int(year_text.strip("()"))

                rating = None
                rating_cell = movie.find("td", class_="ratingColumn imdbRating")
                if rating_cell and rating_cell.strong:
                    rating = float(rating_cell.strong.get_text(strip=True))

            # We'll keep summary empty for now (you can add extra scraping later)
            summary = ""

            print(f"[INFO] Movie #{count+1}: {title!r}, year={year}, rating={rating}")
            db.add(Movie(
                title=title,
                summary=summary,
                rating=rating,
                year=year
            ))
            count += 1

        except Exception as e:
            print(f"[ERROR] Failed to parse movie row: {e}")
            continue

    print(f"[INFO] Parsed {count} movies, committing to DB...")
    try:
        db.commit()
        print(f"[INFO] Commit successful, {count} movies saved.")
    except Exception as e:
        print("[ERROR] DB commit failed:", e)
    finally:
        db.close()
        print("[INFO] DB session closed.")


if __name__ == "__main__":
    scrape_top_movies_with_selenium(limit=250)
