from api.schemas import DomainRequest
import os
import anthropic
import json
from dotenv import load_dotenv
import time
from .fetch_grants import fetch_grant_data
from .pinecone_db import upsert, connect_pinecone
from .supabase import ingest_batch, downstream_failure, get_supabase_conn
from .celery_app import app
from .write_to_graph import ingest_graph_nodes, connect_neo4j_db

load_dotenv()

@app.task
def run_injest_pipeline(inj_data: dict):
    ids = []
    chunks = []
    inj_domain = DomainRequest(**inj_data)

    try:
        supabase_conn = get_supabase_conn()
        pinecone_index = connect_pinecone()
        neo4j_index = connect_neo4j_db()
        neo4j_index.verify_connectivity()
    except Exception as e:
        print(f"error when connecting to services: {e}")
    
    try:
        data, domain = fetch_grant_data(inj_domain)
        print(f"fetched {len(data)} awards")
        print("generating topics and methods")
        gen_topics_methods(data)
        print("generated topics and methods")
        chunks, ids = ingest_batch(data, supabase_conn)
        print(f"injested and generated {len(chunks)} chunks")
        upsert(chunks, domain, pinecone_index)
        print("successful pinecone upsert")
        ingest_graph_nodes(data, neo4j_index)
        print("Successful Neo4j insert")

    except Exception as e:
        if ids:
            downstream_failure(ids, supabase_conn)
        print(f"Error: {e}")
        raise e
    print("successful pinecone upsert")
    return len(chunks)

def gen_topics_methods(data: list[dict]) -> None:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    batch_size = 5

    for i in range(0, len(data), batch_size):
        batch = data[i: i + batch_size]

        batch_input = [
            {"award_id": a["award_id"], "title": a["title"], "abstract": a["abstract"]}
            for a in batch
        ]

        prompt = f"""Given the following grant abstracts, return a JSON array where each element has:
- "award_id": the award id as given
- "topics": array of 2-3 short research topic tags (2-4 words each)
- "methods": array of 1-3 research methods or technologies used (empty array if unclear)

Return only a JSON array, no preamble, no markdown fences.

Abstracts:
{json.dumps(batch_input, indent=2)}"""

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = response.content[0].text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            results = json.loads(raw)

            result_map = {r["award_id"]: r for r in results}
            for award in batch:
                matched = result_map.get(award["award_id"], {})
                award["topics"] = _normalize_tags(matched.get("topics", []))
                award["methods"] = _normalize_tags(matched.get("methods", []))

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"LLM extraction failed for batch {i // batch_size}: {e} — defaulting to empty")
            for award in batch:
                award.setdefault("topics", [])
                award.setdefault("methods", [])

        if i + batch_size < len(data):
            time.sleep(12)


def _normalize_tags(tags: list) -> list[str]:
    seen = set()
    out = []
    for t in tags:
        if not isinstance(t, str):
            continue
        normalized = " ".join(t.strip().split()).title()
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out
