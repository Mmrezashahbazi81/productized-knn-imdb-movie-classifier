import requests
import re
import time
from bs4 import BeautifulSoup
from database import SessionLocal, engine, Base
from models import Movie

# Ensure DB tables exist (Movie model registered via models import)
Base.metadata.create_all(bind=engine)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9"
}

BASE_URL = "https://m.imdb.com"

def scrape_top_movies(limit=10):

    url = f"{BASE_URL}/chart/top/"
    print(f"Starting scrape for top movies, limit={limit}")
    response = requests.get(url, headers=headers, timeout=(5,10))
    if response.status_code != 200:
        raise SystemExit(f"Failed to fetch {url}: {response.status_code}")

    soup = BeautifulSoup(response.content, "html.parser")

    # IMDb list container (robust against class name changes)
    movie_list_parent = soup.find("ul", class_=re.compile(r"ipc-metadata-list.*"))
    if not movie_list_parent:
        with open("imdb_debug.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        raise SystemExit("Movie list not found. Saved imdb_debug.html")

    movie_list = movie_list_parent.find_all(
        "li", class_="ipc-metadata-list-summary-item"
    )

    db = SessionLocal()
    count = 0

    for movie in movie_list:
        if count >= limit:
            break

        # ---------- TITLE ----------
        title_element = movie.find("h3", class_="ipc-title__text")
        if title_element:
            full_title = title_element.get_text(strip=True)
            movie_name = ".".join(full_title.split(".")[1:]).strip() if "." in full_title else full_title
        else:
            continue  # title is mandatory

        # ---------- YEAR ----------
        movie_year = None
        year_element = movie.find(
            "span",
            class_=re.compile(r"cli-title-metadata-item")
        )
        if year_element:
            ym = re.search(r"(19|20)\d{2}", year_element.get_text())
            if ym:
                movie_year = int(ym.group(0))
        else:
            # fallback: try to find any 4-digit year in the movie text
            ym2 = re.search(r"(19|20)\d{2}", movie.get_text())
            if ym2:
                movie_year = int(ym2.group(0))

        # ---------- RATING ----------
        movie_rating = None
        rating_element = movie.find(
            "span",
            class_=re.compile(r"ipc-rating-star|AggregateRating|rating")
        )
        if rating_element:
            rm = re.search(r"(\d+(?:\.\d+)?)", rating_element.get_text(strip=True))
            if rm:
                movie_rating = float(rm.group(1))
        else:
            # fallback: try to extract a float from the movie block
            rm2 = re.search(r"(\d+(?:\.\d+)?)", movie.get_text())
            if rm2:
                movie_rating = float(rm2.group(1))

        # ---------- SUMMARY LINK ----------
        link_element = movie.find("a", class_="ipc-title-link-wrapper")
        summary_link = link_element.get("href") if link_element else None

        # ---------- SUMMARY ----------
        summary = ""
        if summary_link:
            try:
                summary_page = requests.get(
                    BASE_URL + summary_link,
                    headers=headers,
                    timeout=(5,10)
                )
                if summary_page.status_code == 200:
                    soup2 = BeautifulSoup(summary_page.content, "html.parser")
                    summary_element = soup2.find(
                        "div", class_="ipc-html-content-inner-div"
                    )
                    summary = summary_element.get_text(strip=True) if summary_element else ""
            except requests.exceptions.RequestException as e:
                print(f"Warning: failed to fetch summary for {summary_link}: {e}")
                summary = ""
            # polite delay to avoid blocking or rate-limits
            time.sleep(0.2)

        # ---------- INSERT INTO DB ----------
        print(f"Movie #{count+1}: title={movie_name!r}, year={movie_year}, rating={movie_rating}, link={summary_link}")
        print("Summary preview:", summary[:200])
        db.add(Movie(
            title=movie_name,
            summary=summary,
            rating=movie_rating,
            year=movie_year
        ))
        print("Added to session")

        count += 1

    print(f"Loop finished, processed {count} movies — preparing to commit")

    try:
        print("Attempting to commit to DB now...")
        db.commit()
        print(f"Committed {count} movies to DB")
        # verify inserted records
        db_verify = SessionLocal()
        inserted = db_verify.query(Movie).order_by(Movie.id.desc()).limit(count).all()
        print("Inserted records (most recent first):")
        for m in inserted:
            preview = (m.summary[:140] + "...") if m.summary and len(m.summary) > 140 else m.summary
            print(f" - id={m.id}, title={m.title!r}, year={m.year}, rating={m.rating}, summary={preview}")
        db_verify.close()
    except Exception as e:
        print("DB commit failed:", e)
    finally:
        db.close()


if __name__ == "__main__":
    scrape_top_movies(limit=10)
