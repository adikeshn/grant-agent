from pinecone import Pinecone
from chunk import bge_m3_embed
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX_NAME")

if index_name is None:
    raise ValueError("PINECONE_INDEX_NAME environment variable is not set")

pc = Pinecone(api_key=api_key)
index = pc.Index(index_name)

def upsert(chunks: list[dict], namespace: str):
    vectors = []
    for chunk in chunks:
        embed = bge_m3_embed(chunk["text"])
        vectors.append({
            "id": chunk["id"],
            "values": embed,
            "metadata": chunk["metadata"]
        })
    
    index.upsert(
        vectors=vectors,
        namespace=namespace
    )