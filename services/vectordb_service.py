from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import faiss
import numpy as np
import requests
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
import os
import openai

# Initialize FastAPI app
app = FastAPI()

# Load openai
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API Key. Set OPENAI_API_KEY as an environment variable or in a .env file.")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize FAISS index
embedding_size = 384  # Model output size
index = faiss.IndexFlatL2(embedding_size)  # L2 distance search
doc_store = {}  # Stores chunk mappings (index -> text)

# Wikipedia API URL
WIKI_API_URL = "https://en.wikipedia.org/w/api.php"

class IndexRequest(BaseModel):
    article_titles: List[str]

class QueryRequest(BaseModel):
    query: str
    top_k: int = 3

def fetch_wikipedia_text(title):
    """Fetches Wikipedia article text by title"""
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "explaintext": True,
        "titles": title
    }
    response = requests.get(WIKI_API_URL, params=params).json()
    
    pages = response.get("query", {}).get("pages", {})
    for page in pages.values():
        return page.get("extract", "")
    
    return ""

def chunk_text(text, chunk_size=512, overlap=50):
    """Splits text into smaller chunks"""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return splitter.split_text(text)

def get_embedding(text):
    """Converts text into vector embedding"""
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )
    return np.array(response.data[0].embedding)

def index_articles(article_titles):
    """Fetches, chunks, and indexes Wikipedia articles"""
    global doc_store, index

    all_embeddings = []
    doc_store.clear()  # Reset stored chunks
    
    for title in article_titles:
        print(title)
        text = fetch_wikipedia_text(title)
        print("fetched wikipedia article from title")
        if not text:
            continue
        
        chunks = chunk_text(text)
        print("chunked article text")
        chunk_embeddings = [get_embedding(chunk) for chunk in chunks]
        print("embedded chunks")

        for i, emb in enumerate(chunk_embeddings):
            doc_store[len(doc_store)] = chunks[i]
            all_embeddings.append(emb)
        print("stored embeddings in vdb")
    
    if all_embeddings:
        index.reset()  # Clear FAISS index
        index.add(np.array(all_embeddings, dtype=np.float32))

@app.post("/index")
def index_articles_api(request: IndexRequest):
    print("/index")
    """Endpoint to index Wikipedia articles"""
    index_articles(request.article_titles)
    print(f"Indexed {len(request.article_titles)} articles into {len(doc_store)} chunks.")
    return {"status": "Indexing complete", "num_chunks": len(doc_store)}

@app.post("/search")
def search_faiss(request: QueryRequest):
    """Performs FAISS similarity search"""
    if not doc_store:
        raise HTTPException(status_code=400, detail="No articles indexed. Call /index first.")
    
    query_embedding = np.array([get_embedding(request.query)], dtype=np.float32)
    distances, indices = index.search(query_embedding, request.top_k)

    results = [{"text": doc_store[idx]} for idx in indices[0]]
    return {"results": results}
