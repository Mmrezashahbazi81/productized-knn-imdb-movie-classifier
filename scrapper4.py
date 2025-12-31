import requests
import re
import time
from bs4 import BeautifulSoup
from database import SessionLocal, engine, Base
from models import Movie

Base.metadata.create_all(bind=engine)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0",
    "Accept-Language": "en-US,en;q=0.9"
}

BASE_URL = "https://www.imdb.com"

def scrape_top_movies(limit=250):
    print(f"[INFO] Starting scrape for top movies, limit={limit}")
    url = f"{BASE_URL}/chart/top/"
    response = requests.get(url, headers=headers, timeout=(5,10))
    print("[DEBUG] Request status:", response.status_code)
    if response.status_code != 200:
        raise SystemExit(f"[ERROR] Failed to fetch {url}: {response.status_code}")

    soup = BeautifulSoup(response.content, "html.parser")
    print("[DEBUG] Page title:", soup.title.string)

    # Try both layouts
    movie_list_parent = soup.find("tbody", class_="lister-list")
    if movie_list_parent:
        movie_list = movie_list_parent.find_all("tr")
        layout = "desktop"
    else:
        movie_list_parent = soup.find("ul", class_=re.compile(r"ipc-metadata-list.*"))
        movie_list = movie_list_parent.find_all("li", class_="ipc-metadata-list-summary-item") if movie_list_parent else []
        layout = "modern"

    print(f"[INFO] Using {layout} layout, found {len(movie_list)} movies")

    if not movie_list:
        with open("imdb_debug.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        raise SystemExit("[ERROR] Movie list not found. Saved imdb_debug.html")

    db = SessionLocal()
    count = 0

    for movie in movie_list:
        if count >= limit:
            break

        try:
            if layout == "desktop":
                # Desktop selectors
                title = movie.select_one("td.titleColumn a").get_text(strip=True)
                year_text = movie.select_one("td.titleColumn span.secondaryInfo").get_text(strip=True)
                year = int(year_text.strip("()"))
                rating = float(movie.select_one("td.ratingColumn.imdbRating strong").get_text(strip=True))
                link = movie.select_one("td.titleColumn a")["href"]

            else:
                # Modern selectors
                title_element = movie.find("h3", class_="ipc-title__text")
                title = title_element.get_text(strip=True) if title_element else None
                year = None
                year_element = movie.find("span", class_=re.compile(r"cli-title-metadata-item"))
                if year_element:
                    ym = re.search(r"(19|20)\d{2}", year_element.get_text())
                    if ym:
                        year = int(ym.group(0))
                rating = None
                rating_element = movie.find("span", class_=re.compile(r"ipc-rating-star|AggregateRating|rating"))
                if rating_element:
                    rm = re.search(r"(\d+(?:\.\d+)?)", rating_element.get_text(strip=True))
                    if rm:
                        rating = float(rm.group(1))
                link_element = movie.find("a", class_="ipc-title-link-wrapper")
                link = link_element.get("href") if link_element else None

            summary_url = BASE_URL + link if link else None
            summary = ""
            if summary_url:
                try:
                    summary_page = requests.get(summary_url, headers=headers, timeout=(5,10))
                    if summary_page.status_code == 200:
                        soup2 = BeautifulSoup(summary_page.content, "html.parser")
                        summary_element = soup2.find("div", class_="ipc-html-content-inner-div")
                        summary = summary_element.get_text(strip=True) if summary_element else ""
                except Exception as e:
                    print(f"[WARN] Failed to fetch summary for {title}: {e}")
                time.sleep(0.2)

            print(f"[INFO] Movie #{count+1}: {title} ({year}) Rating={rating}")
            print("[DEBUG] Summary preview:", summary[:120])

            db.add(Movie(title=title, summary=summary, rating=rating, year=year))
            count += 1

        except Exception as e:
            print(f"[ERROR] Failed to parse movie row: {e}")
            continue

    print(f"[INFO] Loop finished, processed {count} movies — preparing to commit")

    try:
        db.commit()
        print(f"[INFO] Committed {count} movies to DB")
    except Exception as e:
        print("[ERROR] DB commit failed:", e)
    finally:
        db.close()

if __name__ == "__main__":
    scrape_top_movies(limit=250)
