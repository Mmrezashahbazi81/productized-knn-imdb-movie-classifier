import time
import re
import undetected_chromedriver as uc
from bs4 import BeautifulSoup

from database import SessionLocal, engine, Base
from models import Movie

Base.metadata.create_all(bind=engine)

BASE_URL = "https://www.imdb.com"


def load_page_with_selenium(url, wait=5):
    print("[INFO] Starting undetected Chrome...")

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = uc.Chrome(options=options)

    print(f"[INFO] Opening URL: {url}")
    driver.get(url)

    print(f"[INFO] Waiting {wait} seconds for JS to load...")
    time.sleep(wait)

    # Scroll to bottom
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    print("[INFO] Page fully loaded.")
    return driver, driver.page_source


def extract_summary(driver, movie_url):
    try:
        driver.get(movie_url)
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        summary = soup.select_one("span[data-testid='plot-l']")
        if summary:
            return summary.get_text(strip=True)

        summary = soup.find("span", class_=re.compile(r"sc-16ede01"))
        if summary:
            return summary.get_text(strip=True)

        return ""
    except Exception as e:
        print(f"[WARN] Could not extract summary from {movie_url}: {e}")
        return ""


def scrape_top_movies(limit=250):
    print(f"[INFO] Starting IMDb Top 250 scrape (limit={limit})")

    url = f"{BASE_URL}/chart/top/"
    driver, html = load_page_with_selenium(url, wait=7)

    soup = BeautifulSoup(html, "html.parser")
    print("[DEBUG] Page title:", soup.title.string if soup.title else "NO TITLE")

    movie_list_parent = soup.find("ul", class_=re.compile(r"ipc-metadata-list"))
    layout = None

    if movie_list_parent:
        movie_list = movie_list_parent.find_all("li", class_="ipc-metadata-list-summary-item")
        layout = "modern-ul-li"
    else:
        table = soup.find("tbody", class_="lister-list")
        if table:
            movie_list = table.find_all("tr")
            layout = "classic-table"
        else:
            movie_list = []

    print(f"[INFO] Layout detected: {layout}, movies found: {len(movie_list)}")

    if not movie_list:
        print("[ERROR] No movie list found.")
        driver.quit()
        return

    db = SessionLocal()
    count = 0

    for movie in movie_list:
        if count >= limit:
            break

        try:
            if layout == "modern-ul-li":
                title_el = movie.find("h3", class_="ipc-title__text")
                if not title_el:
                    continue

                full_title = title_el.get_text(strip=True)
                title = ".".join(full_title.split(".")[1:]).strip() if "." in full_title else full_title

                year = None
                year_el = movie.find("span", class_=re.compile(r"cli-title-metadata-item"))
                if year_el:
                    ym = re.search(r"(19|20)\d{2}", year_el.get_text())
                    if ym:
                        year = int(ym.group(0))

                rating = None
                rating_el = movie.find("span", class_=re.compile(r"ipc-rating-star|AggregateRating|rating"))
                if rating_el:
                    rm = re.search(r"(\d+(?:\.\d+)?)", rating_el.get_text(strip=True))
                    if rm:
                        rating = float(rm.group(1))

                link_el = movie.find("a", class_="ipc-title-link-wrapper")
                relative_link = link_el.get("href") if link_el else None

            else:
                title_cell = movie.find("td", class_="titleColumn")
                if not title_cell or not title_cell.a:
                    continue

                title = title_cell.a.get_text(strip=True)

                year = None
                year_span = title_cell.find("span", class_="secondaryInfo")
                if year_span:
                    year = int(year_span.get_text(strip=True).strip("()"))

                rating = None
                rating_cell = movie.find("td", class_="ratingColumn imdbRating")
                if rating_cell and rating_cell.strong:
                    rating = float(rating_cell.strong.get_text(strip=True))

                relative_link = title_cell.a["href"]

            movie_url = BASE_URL + str(relative_link) if relative_link else None

            # -------------------------
            # Extract summary
            # -------------------------
            summary = extract_summary(driver, movie_url) if movie_url else ""

            print(f"[INFO] Movie #{count+1}: {title} ({year}) Rating={rating}")
            print("[DEBUG] Summary:", summary[:120])

            db.add(Movie(
                title=title,
                summary=summary,
                rating=rating,
                year=year
            ))

            count += 1

        except Exception as e:
            print(f"[ERROR] Failed to parse movie: {e}")
            continue

    print(f"[INFO] Parsed {count} movies. Saving to DB...")

    try:
        db.commit()
        print("[INFO] Commit successful.")
    except Exception as e:
        print("[ERROR] Commit failed:", e)
    finally:
        db.close()
        driver.quit()
        print("[INFO] Scraper finished.")
