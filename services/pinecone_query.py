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

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

def query_index(query, index_name):

    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(index_name)

    embedding = pc.inference.embed(
        model="multilingual-e5-large",
        inputs=[query],
        parameters={
            "input_type": "query"
        }
    )

    results = index.query(
        namespace="ns1",
        vector=embedding[0].values,
        top_k=3,
        include_values=False,
        include_metadata=True
    )

    return results


def print_results(results):
    for match in results['matches']:
        print(f"{match['metadata']['title']}, {match['id']}")
        print(match['metadata']['text'])
        print()

if __name__ == "__main__":
    index_name = "json-cleaned-sample"
    query = "Claude Monet and Impressionism"
    results = query_index(query, index_name)
    print_results(results)    
