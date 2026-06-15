from pinecone import Pinecone
from dotenv import load_dotenv
from FlagEmbedding import BGEM3FlagModel
import os


load_dotenv()

api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX_NAME")

if index_name is None:
    raise ValueError("PINECONE_INDEX_NAME environment variable is not set")

model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)

pc = Pinecone(api_key=api_key)
index = pc.Index(index_name)

def bge_m3_embed(text: str):
    output = model.encode([text], max_length=8192)
    return [float(x) for x in output['dense_vecs'][0]]



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

def dense_retrieval(query_txt: str, namespace: str, k: int):
    q_embedding = bge_m3_embed(query_txt)
    results = index.query(
        namespace=namespace,
        vector=q_embedding,
        top_k=k,
        include_metadata=True
    )
    return results