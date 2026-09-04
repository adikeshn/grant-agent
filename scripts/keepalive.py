import os
import sys
import requests
from neo4j import GraphDatabase

def ping_neo4j():
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS c LIMIT 1")
        print("Neo4j OK, node count sample:", result.single()["c"])
    driver.close()

def ping_supabase():
    # Targets the built-in REST API which reliably registers database activity
    url = f"{os.environ['SUPABASE_URL']}/rest/v1/chunks?select=id&limit=1"
    headers = {
        "apikey": os.environ["SUPABASE_ANON_KEY"],
        "Authorization": f"Bearer {os.environ['SUPABASE_ANON_KEY']}"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print("Supabase REST API OK:", response.json())
    else:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

if __name__ == "__main__":
    failures = []
    try:
        ping_neo4j()
    except Exception as e:
        print(f"Neo4j ping failed: {e}")
        failures.append("neo4j")

    try:
        ping_supabase()
    except Exception as e:
        print(f"Supabase ping failed: {e}")
        failures.append("supabase")

    if failures:
        sys.exit(1)
