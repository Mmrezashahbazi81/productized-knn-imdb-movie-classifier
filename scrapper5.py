import requests
import re
import time
from bs4 import BeautifulSoup
from database import SessionLocal, engine, Base
from models import Movie

Base.metadata.create_all(bind=engine)

def scrape_from_file(html_path: str, limit: int = 250):
    print(f"[INFO] Reading HTML from file: {html_path}")

    # 1) Read file
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 2) Parse with BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    print("[DEBUG] Page title:", soup.title.string if soup.title else "NO TITLE")

    # 3) Find the movie list (your working structure)
    movie_list_parent = soup.find("ul", class_=re.compile(r"ipc-metadata-list.*"))
    if not movie_list_parent:
        print("[ERROR] Could not find <ul> with class 'ipc-metadata-list'")
        with open("imdb_debug_from_file.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        return

    movie_list = movie_list_parent.find_all("li", class_="ipc-metadata-list-summary-item")
    print(f"[INFO] Found {len(movie_list)} movies in HTML file")

    db = SessionLocal()
    count = 0

    for movie in movie_list:
        if count >= limit:
            break

        try:
            # ---------- TITLE ----------
            title_element = movie.find("h3", class_="ipc-title__text")
            if title_element:
                full_title = title_element.get_text(strip=True)
                movie_name = ".".join(full_title.split(".")[1:]).strip() if "." in full_title else full_title
            else:
                print("[WARN] Skipping movie with no title")
                continue  # title is mandatory

            # ---------- YEAR ----------
            movie_year = None
            year_element = movie.find("span", class_=re.compile(r"cli-title-metadata-item"))
            if year_element:
                ym = re.search(r"(19|20)\d{2}", year_element.get_text())
                if ym:
                    movie_year = int(ym.group(0))

            # ---------- RATING ----------
            movie_rating = None
            rating_element = movie.find("span", class_=re.compile(r"ipc-rating-star|AggregateRating|rating"))
            if rating_element:
                rm = re.search(r"(\d+(?:\.\d+)?)", rating_element.get_text(strip=True))
                if rm:
                    movie_rating = float(rm.group(1))

            # ---------- SUMMARY (optional from this HTML) ----------
            # If your saved HTML contains summaries, parse them here.
            # If not, just leave summary empty or a placeholder.
            summary = ""

            print(f"[INFO] Movie #{count+1}: title={movie_name!r}, year={movie_year}, rating={movie_rating}")
            print("[DEBUG] Summary preview:", summary[:120])

            db.add(Movie(
                title=movie_name,
                summary=summary,
                rating=movie_rating,
                year=movie_year
            ))
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
    # Adjust filename if needed
    scrape_from_file("imdb_full.html", limit=250)
