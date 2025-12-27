import requests
import re
from bs4 import BeautifulSoup
from database import SessionLocal
from models import Movie

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9"
}

BASE_URL = "https://m.imdb.com"

def scrape_top_movies(limit=10):

    url = f"{BASE_URL}/chart/top/"
    response = requests.get(url, headers=headers, timeout=10)
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
        year_element = movie.find(
            "span",
            class_=re.compile(r"cli-title-metadata-item")
        )
        movie_year = int(year_element.get_text(strip=True)) if year_element else None

        # ---------- RATING ----------
        rating_element = movie.find(
            "span",
            class_=re.compile(r"ipc-rating-star--imdb")
        )
        movie_rating = float(rating_element.get_text(strip=True).split()[0]) if rating_element else None

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
                    timeout=10
                )
                if summary_page.status_code == 200:
                    soup2 = BeautifulSoup(summary_page.content, "html.parser")
                    summary_element = soup2.find(
                        "div", class_="ipc-html-content-inner-div"
                    )
                    summary = summary_element.get_text(strip=True) if summary_element else ""
            except Exception:
                summary = ""

        # ---------- INSERT INTO DB ----------
        db.add(Movie(
            title=movie_name,
            description=summary,
            rating=movie_rating,
            year=movie_year
        ))

        count += 1

    db.commit()
    db.close()
    print(f"Inserted {count} movies into DB")
