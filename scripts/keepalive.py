import os
import sys
from neo4j import GraphDatabase
import psycopg2

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
    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print("Supabase OK:", cur.fetchone())
    cur.close()
    conn.close()

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
