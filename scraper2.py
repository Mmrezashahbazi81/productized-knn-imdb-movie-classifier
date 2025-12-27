import requests
from bs4 import BeautifulSoup
from database import SessionLocal
from models import Movie

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9"
}

def scrape_top_movies(limit=10):
    
    
    
    url = "https://m.imdb.com/chart/top/"
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise SystemExit(f"Failed to fetch {url}: {response.status_code}")
    
    soup = BeautifulSoup(response.content , "html.parser")

    movie_list = soup.find("ul", class_="ipc-metadata-list").find_all("li", class_="ipc-metadata-list-summary-item")

    db = SessionLocal()
    count = 0
    for movie in movie_list:
        if count >= limit:
            break

        movie_name = " ".join(movie.find("h3", class_="ipc-title__text").text.split()[1:])
        movie_year = movie.find("span", class_="cli-title-metadata-item").get_text().strip()
        movie_rating = movie.find("span", class_="ipc-rating-star").text.split()[0]
        summary_link = movie.find("a", class_="ipc-title-link-wrapper").get("href")

        summary_page = requests.get("https://m.imdb.com" + summary_link, headers=headers)
        soup2 = BeautifulSoup(summary_page.content, "html.parser")
        summary = soup2.find("div", class_="ipc-html-content-inner-div").text

        # Insert into DB
        db.add(Movie(
            title=movie_name,
            description=summary,
            rating=float(movie_rating),
            year=int(movie_year)
        ))
        count += 1

    db.commit()
    db.close()
    print(f"Inserted {count} movies into DB")
