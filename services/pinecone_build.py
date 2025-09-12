# seems unused by other services (testing file?)

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
from pinecone import Pinecone, ServerlessSpec
import json

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")


def load_pinecone_quickstart(data, index_name):
    pc = Pinecone(api_key=PINECONE_API_KEY)

    pc.delete_index(index_name)


    pc.create_index(
        name=index_name,
        dimension=1024,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )

    embeddings = pc.inference.embed(
        model="multilingual-e5-large",
        inputs=[d['text'] for d in data],
        parameters={"input_type": "passage", "truncate": "END"}
    )

    print(embeddings[0])

    while not pc.describe_index(index_name).status['ready']:
        time.sleep(1)

    index = pc.Index(index_name)

    vectors = []
    for d, e in zip(data, embeddings):
        vectors.append({
            "id": d['id'],
            "values": e['values'],
            "metadata": {'text': d['text']}
        })

    index.upsert(
        vectors=vectors,
        namespace="ns1"
    )

    print(index.describe_index_stats())

def chunk_text(text, chunk_size=512, overlap=50):
    """Splits text into smaller chunks"""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return splitter.split_text(text)

def load_jstor(filename, index_name):
    pc = Pinecone(api_key=PINECONE_API_KEY)

    pc.delete_index(index_name)


    pc.create_index(
        name=index_name,
        dimension=1024,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )

    print(f"Pinecone ready, index: {index_name}")

    data_list = []
    with open(filename, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            data = json.loads(line)
            data_list.append(data)

    print(data_list[0])
    print(len(data_list))
    
    while not pc.describe_index(index_name).status['ready']:
        time.sleep(1)

    index = pc.Index(index_name)

    for data in data_list:
        d_title = data.get("title", "[No Title]")
        d_id = data.get("id", "[No ID]")
        print(f"{d_title} , {d_id}")
        chunks = chunk_text(data['fullText'][0])
        print(f"num chunks: {len(chunks)}")
        embeddings = pc.inference.embed(
            model="multilingual-e5-large",
            inputs=[ch for ch in chunks],
            parameters={"input_type": "passage", "truncate": "END"}
        )

        vectors = []
        for ch, e in zip(chunks, embeddings):
            vectors.append({
                "id": d_id,
                "values": e['values'],
                "metadata": {'text': ch, 'title': d_title}
            })

        index.upsert(
            vectors=vectors,
            namespace="ns1"
        )

    print(f"Done loading, final stats:")
    print(index.describe_index_stats())



if __name__ == "__main__":

    # quickstart_data = [
    #     {"id": "vec1", "text": "Apple is a popular fruit known for its sweetness and crisp texture."},
    #     {"id": "vec2", "text": "The tech company Apple is known for its innovative products like the iPhone."},
    #     {"id": "vec3", "text": "Many people enjoy eating apples as a healthy snack."},
    #     {"id": "vec4", "text": "Apple Inc. has revolutionized the tech industry with its sleek designs and user-friendly interfaces."},
    #     {"id": "vec5", "text": "An apple a day keeps the doctor away, as the saying goes."},
    #     {"id": "vec6", "text": "Apple Computer Company was founded on April 1, 1976, by Steve Jobs, Steve Wozniak, and Ronald Wayne as a partnership."}
    # ]

    # load_pinecone(quickstart_data)

    jstor_data = load_jstor("data/artinfo-jstor-cleaned.jsonl", "json-cleaned-sample")