from pinecone import Pinecone
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
import os


load_dotenv()

api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX_NAME")

client = InferenceClient(token=os.getenv("HF_TOKEN"))

def connect_pinecone():
    pc = Pinecone(api_key=api_key)
    if not index_name:
        raise ValueError("Index Name NULL")
    index = pc.Index(index_name)
    return index

def bge_m3_embed(text: str):
    output = client.feature_extraction(text, model="BAAI/bge-m3")
    return [float(x) for x in output]





def upsert(chunks: list[dict], namespace: str, index):
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

def dense_retrieval(query_txt: str, namespace: str, k: int, index):
    q_embedding = bge_m3_embed(query_txt)
    results = index.query(
        namespace=namespace,
        vector=q_embedding,
        top_k=k,
        include_metadata=True
    )
    return results