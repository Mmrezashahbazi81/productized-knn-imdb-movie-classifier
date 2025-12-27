import math
from collections import defaultdict, Counter
import spacy
from database import SessionLocal
from models import Movie

nlp = spacy.load("en_core_web_sm")

def cleaning(summary):
    doc = nlp(summary)
    words = [w for w in doc if not w.is_stop and not w.is_punct]
    return " ".join(w.text for w in words)

def compute_tf(document):
    word_count = len(document)
    word_freq = Counter(document)
    return {word: count / word_count for word, count in word_freq.items()}

def compute_idf(documents):
    idf_dict = defaultdict(int)
    num_documents = len(documents)
    for doc in documents:
        for word in set(doc):
            idf_dict[word] += 1
    return {word: math.log(num_documents / count) + 1 for word, count in idf_dict.items()}

def compute_tf_idf(documents):
    idf_dict = compute_idf(documents)
    tf_idf_documents = []
    for doc in documents:
        tf_dict = compute_tf(doc)
        tf_idf_documents.append({word: tf * idf_dict[word] for word, tf in tf_dict.items()})
    return tf_idf_documents

def cosine_similarity(vec1, vec2):
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum(vec1[x] * vec2[x] for x in intersection)
    sum1 = sum(v ** 2 for v in vec1.values())
    sum2 = sum(v ** 2 for v in vec2.values())
    denominator = math.sqrt(sum1) * math.sqrt(sum2)
    return numerator / denominator if denominator else 0.0

def knn(tf_idf_vectors, new_vector, k=5):
    similarities = [(idx, cosine_similarity(vector, new_vector)) for idx, vector in enumerate(tf_idf_vectors)]
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:k]

def build_classifier():
    db = SessionLocal()
    movies = db.query(Movie).all()
    summaries = [cleaning(m.summary) for m in movies]
    tokenized = [s.split() for s in summaries]
    tf_idf_vectors = compute_tf_idf(tokenized)
    db.close()
    return movies, tf_idf_vectors

def analyze_summary(summary, movies, tf_idf_vectors, k=5):
    cleaned = cleaning(summary)
    token = [cleaned.split()]
    tf_idf_new = compute_tf_idf(token)[0]
    neighbors = knn(tf_idf_vectors, tf_idf_new, k=k)
    return [{"title": movies[idx].title, "similarity": sim} for idx, sim in neighbors]
