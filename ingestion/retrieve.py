
from pinecone_db import dense_retrieval
from supabase import get_bm_25, tokenize, get_conn, get_ids
from sentence_transformers import CrossEncoder
from celery_app import app
model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

@app.task
def retrieve_chunk_rankings(bm25_indexes, domain: str,
                            query_text: str, top_dense: int, top_sparse: int, 
                            top_final: int, rrf_k: int = 60):
    conn = None
    cursor = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # get sparse and dense rankings
        dense_results = dense_retrieval(query_txt=query_text, namespace=domain, k=top_dense)
        chunk_dict = get_ids(domain, cursor)
        if chunk_dict is None:
            raise ValueError("chunk list is None")
        if domain not in bm25_indexes:
            get_bm_25(bm25_indexes, domain, cursor)
        sparse_results = bm25_indexes[domain]["index"].get_top_n(tokenize(query_text), bm25_indexes[domain]["ids"], n=top_sparse)
        
        # calculate reciprocal rank fusion
        print("\n=== DENSE RETRIEVAL RANKINGS ===")
        for rank, match in enumerate(dense_results.matches):
            chunk_dict[match.id][0] += (1 / (rank + 1 + rrf_k))
            print(f"Rank {rank + 1}: {match.id}, {match.score}")

        print("\n=== SPARSE RETRIEVAL RANKINGS ===")
        for rank, item in enumerate(sparse_results, 1):
            chunk_dict[item][0] += (1 / (rank + rrf_k))
            print(f"Rank {rank}: {item}")

        # do reranking with cross encoder
        cross_encode_inp = []
        retrieved_ids = []
        for key, value in chunk_dict.items():
            if value[0] > 0:
                cross_encode_inp.append((query_text, value[1]))
                retrieved_ids.append(key)
        return sorted((zip(retrieved_ids, cross_encode_inp, model.predict(cross_encode_inp))), key=lambda x: x[2], reverse=True)[:top_final], bm25_indexes[domain]


    except Exception as e:
        if conn: conn.rollback()
        print(f"Error during retrieval: {e}")
        raise e

    finally:
        if cursor: cursor.close()
        if conn: conn.close()

query = "what are the breakthroughs in reinforcement learning?"
top_chunks = retrieve_chunk_rankings({}, "reinforcement learning", query, 10, 10, 5, 60)
for id, encode_inp, score in top_chunks:
    print(f"{id} -- {score}")




