from flask import Flask, request, jsonify
from database import SessionLocal
from models import Movie

app = Flask(__name__)

@app.get("/movies")
def get_movies():
    db = SessionLocal()
    movies = db.query(Movie).all()
    return jsonify([{
        "id": m.id,
        "title": m.title,
        "summary": m.summary,
        "rating": m.rating,
        "year": m.year
    } for m in movies])

@app.route("/")
def home():
    return "Welcome to the IMDB API! Try /movies"

from selenium_scraper import scrape_top_movies

@app.post("/scrape")
def scrape_movies():
    #limit = int(request.args.get("limit", 250))
    limit = 250
    scrape_top_movies(limit=limit)
    return {"message": f"Scraped {limit} movies and saved to DB"}


from classifier import build_classifier, analyze_summary

movies, tf_idf_vectors = build_classifier()

@app.post("/predict")
def predict():
    data = request.get_json()
    summary = data.get("summary")
    k = int(data.get("k", 5))
    results = analyze_summary(summary, movies, tf_idf_vectors, k=k)
    return jsonify(results)



if __name__ == "__main__":
    app.run(debug=False)

