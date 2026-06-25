from ingestion.pinecone_db import dense_retrieval
from ingestion.supabase import get_bm_25, tokenize, get_supabase_conn, get_ids
from ingestion.celery_app import app
import json
from sentence_transformers import CrossEncoder

model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def retrieve_chunk_rankings(bm25_indexes, pinecone_index, supabase_conn, domain: str,
                            query_text: str, top_dense: int, top_sparse: int, 
                            top_final: int, rrf_k: int = 60):
    cursor = None
    try:
        cursor = supabase_conn.cursor()

        # get sparse and dense rankings
        dense_results = dense_retrieval(query_txt=query_text, namespace=domain, k=top_dense, index=pinecone_index)
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
        headers = []
        for key, value in chunk_dict.items():
            if value[0] > 0:
                cross_encode_inp.append((query_text, value[1]))
                retrieved_ids.append(key)
                headers.append(value[2])
        return sorted((zip(retrieved_ids, cross_encode_inp, headers, model.predict(cross_encode_inp))), key=lambda x: x[3], reverse=True)[:top_final]


    except Exception as e:
        supabase_conn.rollback()
        print(f"Error during retrieval: {e}")
        raise e

    finally:
        if cursor: cursor.close()


def get_candidate_entities(neo4j_driver, user_query: str, domain: str) -> dict:
    with neo4j_driver.session() as session:
        fuzzy_query = " ".join(f"{word}~" for word in user_query.split())

        candidates = {}

        for entity_type, index_name, label_property in [
            ("topic", "topicNames", "label"),
            ("method", "methodNames", "name"),
            ("directorate", "directorateNames", "name"),
            ("pi", "piNames", "name"),
            ("institution", "institutionNames", "name"),
        ]:
            result = session.run(
                """
                CALL db.index.fulltext.queryNodes($index, $query)
                YIELD node, score
                WHERE score > 0.5
                RETURN node[$prop] AS name, score
                ORDER BY score DESC
                LIMIT 5
                """,
                index=index_name,
                query=fuzzy_query,
                prop=label_property
            )
            candidates[entity_type] = [r["name"] for r in result]

    return candidates

def run_cypher_queries(llm_response, domain, driver):

    raw = llm_response.replace("```json", "").replace("```", "").strip()
    cypher_queries = json.loads(raw)

    results = []
    forbidden_keywords = {"create", "delete", "merge", "set", "remove", "drop"}

    for query_obj in cypher_queries:
        cypher = query_obj["cypher"]
        purpose = query_obj["purpose"]

        cypher_lower = cypher.lower()
        if any(kw in cypher_lower for kw in forbidden_keywords):
            print(f"Rejected unsafe query: {cypher}")
            continue

        if f'"{domain}"' not in cypher:
            print(f"Rejected unscoped query: {cypher}")
            continue

        try:
            with driver.session() as session:
                result = session.run(cypher)
                rows = [dict(r) for r in result]
                results.append({
                    "purpose": purpose,
                    "rows": rows
                })
        except Exception as e:
            print(f"query execution failed: {cypher}")
            continue
    formatted = []
    for r in results:
        lines = [f"# {r['purpose']}"]
        for row in r["rows"]:
            lines.append(", ".join(f"{k}: {v}" for k, v in row.items()))
        formatted.append("\n".join(lines))
    return formatted

